"""The no-container route: llama.cpp's ready-built `llama-server` program, started and stopped by
the harness on this computer only.

For a Windows laptop with no Docker and no virtual machine. The harness starts the server as its
own child process, listening on 127.0.0.1 only, at low priority and with Holly's 2 CPU threads and
4,096-token window, waits until it answers, sends each run of posts to it, reads the server's peak
memory, then stops it. There is no container, so nothing caps the memory: the score compares the
measured peak with Holly's 4 GiB instead.
"""

import ctypes
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from .claims import Post, Providers
from .prompt import reply_schema, system_prompt, user_prompt

HOST = "127.0.0.1"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return int(s.getsockname()[1])


class ServerProcess:
    """One llama-server, bound to this computer only, for the length of one model's run."""

    def __init__(self, command: list[str], model: Path, threads: int, context: int) -> None:
        self.port = _free_port()
        self.url = f"http://{HOST}:{self.port}"
        args = [
            *command,
            "-m", str(model),
            "--host", HOST,
            "--port", str(self.port),
            "-t", str(threads),
            "-tb", str(threads),
            "-c", str(context),
            "-np", "1",
        ]  # fmt: skip
        if os.name == "nt":
            flags = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
            self.proc = subprocess.Popen(  # noqa: S603  a fixed program and our own arguments
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags
            )
        else:
            self.proc = subprocess.Popen(  # noqa: S603
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=lambda: os.nice(19),  # noqa: PLW1509  lowest priority, before exec
            )

    def wait_ready(self, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"llama-server stopped while loading (exit {self.proc.returncode})"
                )
            try:
                with urllib.request.urlopen(f"{self.url}/health", timeout=2) as r:  # noqa: S310
                    if r.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.5)
        raise TimeoutError(f"llama-server was not ready within {timeout_s:.0f} s")

    def peak_mib(self) -> float:
        """The server's peak memory so far, in MiB; 0 where the platform gives no reading."""
        if sys.platform == "win32":
            return _windows_peak_mib(self.proc)
        try:
            for line in Path(f"/proc/{self.proc.pid}/status").read_text().splitlines():
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) / 1024
        except OSError:
            pass
        return 0.0

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(10)


def _windows_peak_mib(proc: subprocess.Popen[bytes]) -> float:
    class Counters(ctypes.Structure):
        _fields_ = [  # noqa: RUF012  the layout Windows defines
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    handle = ctypes.c_void_p(int(proc._handle))  # type: ignore[attr-defined]  # noqa: SLF001
    ok = ctypes.windll.kernel32.K32GetProcessMemoryInfo(  # type: ignore[attr-defined]
        handle, ctypes.byref(counters), counters.cb
    )
    return counters.PeakWorkingSetSize / (1024 * 1024) if ok else 0.0


class ServerBackend:
    """Sends each run of posts to the local llama-server, with the reply held to the schema and
    temperature 0, as `LlamaBackend` does inside the container."""

    def __init__(self, url: str, name: str, max_tokens: int, timeout_s: float = 600) -> None:
        self.name = name
        self._url = f"{url}/v1/chat/completions"
        self._max_tokens = max_tokens
        self._timeout = timeout_s

    def extract(self, thread_id: str, posts: tuple[Post, ...], providers: Providers) -> str:
        body = json.dumps(
            {
                "messages": [
                    {"role": "system", "content": system_prompt(providers)},
                    {"role": "user", "content": user_prompt(posts, providers)},
                ],
                "temperature": 0.0,
                "max_tokens": self._max_tokens,
                "response_format": {"type": "json_object", "schema": reply_schema()},
            }
        ).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310  always http://127.0.0.1
            self._url, data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as r:  # noqa: S310
            reply = json.loads(r.read().decode("utf-8"))
        return str(reply["choices"][0]["message"]["content"] or "")
