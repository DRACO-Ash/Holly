"""Runs one backend over every thread in a child process, the way Holly would, and records what
it pulled out, what the checks kept, how long each thread took and the child's peak memory.

The child gets text in and hands results back; it opens no database. Run the trial container with
`--network none` so it has no network either, as the Handover design requires.

Holly has 4 GiB and 2 CPUs in all (2000m), shared with its web app and background loops. So the
child lowers its own priority, as it would in Holly, and while it runs the parent times a small
fixed task at normal priority: how much slower that task gets is a guide to how sluggish Holly's
pages would feel during the run.
"""

import hashlib
import json
import multiprocessing as mp
import os
import statistics
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .backend import Backend, LlamaBackend, StubBackend
from .claims import Providers, Thread, check, parse_claims
from .server import ServerBackend, ServerProcess
from .threads import chunks


@dataclass
class ModelSpec:
    kind: str  # "llama" (in the container), "server" (llama-server, no container) or "stub"
    path: str
    server: tuple[str, ...] = ()  # the command that starts llama-server, for kind "server"
    threads: int = 2
    context: int = 4096
    max_tokens: int = 768
    chunk_chars: int = 8000
    nice: int = 19


@dataclass
class ThreadResult:
    thread_id: str
    seconds: float
    chunks: int
    claims: list[dict[str, Any]] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    unparsed_replies: int = 0


@dataclass
class RunResult:
    model: str
    load_seconds: float
    peak_rss_mib: float
    threads: list[ThreadResult]
    error: str = ""
    probe: dict[str, float] = field(default_factory=dict)


def _build(spec: ModelSpec) -> Backend:
    if spec.kind == "stub":
        return StubBackend(Path(spec.path))
    return LlamaBackend(Path(spec.path), spec.threads, spec.context, spec.max_tokens)


def _read_thread(
    backend: Backend, thread: Thread, providers: Providers, spec: ModelSpec
) -> ThreadResult:
    started = time.monotonic()
    runs = chunks(thread, spec.chunk_chars)
    result = ThreadResult(thread_id=thread.thread_id, seconds=0.0, chunks=len(runs))
    for run in runs:
        text = backend.extract(thread.thread_id, run, providers)
        try:
            data = json.loads(text)
        except ValueError:
            result.unparsed_replies += 1
            continue
        claims, refused = parse_claims(data)
        result.refused.extend(refused)
        for claim in claims:
            verdict = check(claim, thread, providers)
            result.claims.append({**asdict(claim), "result": verdict.reason()})
    result.seconds = round(time.monotonic() - started, 2)
    return result


def _child(spec: ModelSpec, threads: list[Thread], providers: Providers, out: Any) -> None:
    try:
        if spec.nice and hasattr(os, "nice"):
            os.nice(spec.nice)  # yield the CPUs to Holly's own work, as the run would in Holly
        started = time.monotonic()
        backend = _build(spec)
        load = round(time.monotonic() - started, 2)
        results = [_read_thread(backend, t, providers, spec) for t in threads]
        peak = _own_peak_mib()
        out.put(asdict(RunResult(backend.name, load, round(peak, 1), results)))
    except Exception as exc:  # noqa: BLE001  any failure is reported, never hidden
        out.put(
            asdict(RunResult(Path(spec.path).name, 0.0, 0.0, [], f"{type(exc).__name__}: {exc}"))
        )


def _own_peak_mib() -> float:
    try:
        import resource  # noqa: PLC0415  not on Windows

        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KiB on Linux
    except ImportError:
        return 0.0


def _run_server(
    spec: ModelSpec, threads: list[Thread], providers: Providers, timeout_s: float
) -> dict[str, Any]:
    """The no-container route: start llama-server, read every thread through it, stop it."""
    name = Path(spec.path).name
    server = None
    probe = None
    try:
        started = time.monotonic()
        server = ServerProcess(list(spec.server), Path(spec.path), spec.threads, spec.context)
        server.wait_ready(min(timeout_s, 600))
        load = round(time.monotonic() - started, 2)
        probe = _Probe()
        probe.start()
        backend = ServerBackend(server.url, name, spec.max_tokens)
        results = [_read_thread(backend, t, providers, spec) for t in threads]
        peak = server.peak_mib()
        result = asdict(RunResult(name, load, round(peak, 1), results))
    except Exception as exc:  # noqa: BLE001  any failure is reported, never hidden
        result = asdict(RunResult(name, 0.0, 0.0, [], f"{type(exc).__name__}: {exc}"))
    finally:
        if server is not None:
            server.stop()
    result["probe"] = probe.stop() if probe else {}
    return result


_PROBE_DATA = b"\x00" * (256 * 1024)


def _probe_ms() -> float:
    """Milliseconds for a small fixed piece of work, standing in for one of Holly's requests."""
    started = time.perf_counter()
    for _ in range(8):
        hashlib.sha256(_PROBE_DATA).digest()
    return (time.perf_counter() - started) * 1000


class _Probe:
    """Times the fixed task twice a second at normal priority while the child runs."""

    def __init__(self) -> None:
        self.baseline = statistics.median(_probe_ms() for _ in range(15))
        self.samples: list[float] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.wait(0.5):
            self.samples.append(_probe_ms())

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> dict[str, float]:
        self._stop.set()
        self._thread.join(5)
        if not self.samples:
            return {"baseline_ms": round(self.baseline, 2)}
        p95 = sorted(self.samples)[max(0, int(len(self.samples) * 0.95) - 1)]
        return {
            "baseline_ms": round(self.baseline, 2),
            "p95_ms": round(p95, 2),
            "slowdown": round(p95 / self.baseline, 2) if self.baseline else 0.0,
        }


def run_model(
    spec: ModelSpec, threads: list[Thread], providers: Providers, timeout_s: float
) -> dict[str, Any]:
    """The child's results, or an error when it crashed or overran `timeout_s`, with how much
    slower the parent's fixed task ran meanwhile."""
    if spec.kind == "server":
        return _run_server(spec, threads, providers, timeout_s)
    ctx = mp.get_context("spawn")
    out = ctx.Queue()
    probe = _Probe()
    child = ctx.Process(target=_child, args=(spec, threads, providers, out))
    child.start()
    probe.start()
    try:
        result: dict[str, Any] = out.get(timeout=timeout_s)
    except Exception:  # noqa: BLE001  queue.Empty on timeout, or the child died
        probe.stop()
        child.terminate()
        child.join(5)
        return asdict(
            RunResult(
                Path(spec.path).name,
                0.0,
                0.0,
                [],
                f"no result within {timeout_s:.0f} s or the child died (exit {child.exitcode})",
            )
        )
    child.join(30)
    result["probe"] = probe.stop()
    return result
