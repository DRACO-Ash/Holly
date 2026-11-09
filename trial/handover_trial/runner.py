"""Runs one backend over every thread in a child process, the way Holly would, and records what
it pulled out, what the checks kept, how long each thread took and the child's peak memory.

The child gets text in and hands results back; it opens no database. Run the trial container with
`--network none` so it has no network either, as the Handover design requires.
"""

import json
import multiprocessing as mp
import resource
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .backend import Backend, LlamaBackend, StubBackend
from .claims import Providers, Thread, check, parse_claims
from .threads import chunks


@dataclass
class ModelSpec:
    kind: str  # "llama" or "stub"
    path: str
    threads: int = 6
    context: int = 8192
    max_tokens: int = 1024
    chunk_chars: int = 12000


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
        started = time.monotonic()
        backend = _build(spec)
        load = round(time.monotonic() - started, 2)
        results = [_read_thread(backend, t, providers, spec) for t in threads]
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024  # KiB on Linux
        out.put(asdict(RunResult(backend.name, load, round(peak, 1), results)))
    except Exception as exc:  # noqa: BLE001  any failure is reported, never hidden
        out.put(
            asdict(RunResult(Path(spec.path).name, 0.0, 0.0, [], f"{type(exc).__name__}: {exc}"))
        )


def run_model(
    spec: ModelSpec, threads: list[Thread], providers: Providers, timeout_s: float
) -> dict[str, Any]:
    """The child's results, or an error when it crashed or overran `timeout_s`."""
    ctx = mp.get_context("spawn")
    out = ctx.Queue()
    child = ctx.Process(target=_child, args=(spec, threads, providers, out))
    child.start()
    try:
        result: dict[str, Any] = out.get(timeout=timeout_s)
    except Exception:  # noqa: BLE001  queue.Empty on timeout, or the child died
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
    return result
