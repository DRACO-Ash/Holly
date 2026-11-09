"""Command line for the Handover local-model trial.

    python -m handover_trial dry-run --out results-dry
    python -m handover_trial convert --export raw/123.json --channel geo-ops --users users.json --out threads/123.json
    python -m handover_trial run --threads threads --keys keys --providers providers.json \\
        --model models/a.gguf --model models/b.gguf \\
        --holly-peak-gib <measured> --shift-threads <typical> --out results
"""

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from .claims import Providers
from .runner import ModelSpec, run_model
from .score import Load, Marks, load_keys, report, score
from .threads import convert_mattermost, load_threads

HERE = Path(__file__).resolve().parent.parent
SAMPLES = HERE / "samples"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _versions() -> str:
    try:
        import llama_cpp  # noqa: PLC0415

        return f"llama-cpp-python {llama_cpp.__version__}"
    except ImportError:
        return "llama-cpp-python not installed"


def _run(args: argparse.Namespace, specs: list[ModelSpec]) -> int:
    threads = load_threads(Path(args.threads))
    keys = load_keys(Path(args.keys))
    providers = Providers.from_json(json.loads(Path(args.providers).read_text(encoding="utf-8")))
    missing = sorted(set(keys) - {t.thread_id for t in threads})
    if missing:
        print(f"answer keys with no thread file: {missing}", file=sys.stderr)
        return 2
    load = Load(args.limit_gib, args.holly_peak_gib, args.shift_threads)
    marks = Marks()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "Run at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "Python": platform.python_version(),
        "Runtime": _versions(),
        "Threads": str(len(threads)),
        "CPU threads per model": str(args.cpu_threads),
    }
    scores = []
    for spec in specs:
        if spec.kind == "llama":
            meta[f"SHA-256 of {Path(spec.path).name}"] = _sha256(Path(spec.path))
        print(f"running {spec.path} ...", flush=True)
        run = run_model(spec, threads, providers, timeout_s=args.timeout_s)
        (out / f"run-{Path(spec.path).stem}.json").write_text(
            json.dumps(run, indent=2), encoding="utf-8"
        )
        scores.append(score(run, threads, keys, providers, load, marks))
    (out / "scores.json").write_text(json.dumps(scores, indent=2), encoding="utf-8")
    (out / "report.md").write_text(report(scores, load, marks, meta), encoding="utf-8")
    print((out / "report.md").read_text(encoding="utf-8"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="handover_trial")
    sub = parser.add_subparsers(dest="cmd", required=True)

    conv = sub.add_parser("convert", help="Mattermost thread export to the trial format")
    conv.add_argument("--export", required=True)
    conv.add_argument("--channel", default="")
    conv.add_argument("--users", help="JSON map of Mattermost user ids to display names")
    conv.add_argument("--out", required=True)

    for name in ("run", "dry-run"):
        p = sub.add_parser(name)
        dry = name == "dry-run"
        p.add_argument(
            "--threads", default=str(SAMPLES / "threads") if dry else None, required=not dry
        )
        p.add_argument("--keys", default=str(SAMPLES / "keys") if dry else None, required=not dry)
        p.add_argument(
            "--providers",
            default=str(SAMPLES / "providers.json") if dry else None,
            required=not dry,
        )
        p.add_argument("--model", action="append", default=[], help="GGUF file; repeat per model")
        p.add_argument("--stub", default=str(SAMPLES / "stub-replies.json") if dry else None)
        p.add_argument(
            "--holly-peak-gib",
            type=float,
            required=not dry,
            default=1.0 if dry else None,
            help="Holly's own measured peak memory in GiB (dry run: 1.0, a placeholder)",
        )
        p.add_argument(
            "--shift-threads",
            type=int,
            required=not dry,
            default=10 if dry else None,
            help="threads in a typical shift's end-of-shift run (dry run: 10, a placeholder)",
        )
        p.add_argument("--limit-gib", type=float, default=8.0)
        p.add_argument("--cpu-threads", type=int, default=6)
        p.add_argument("--context", type=int, default=8192)
        p.add_argument("--timeout-s", type=float, default=3600.0)
        p.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    if args.cmd == "convert":
        users = json.loads(Path(args.users).read_text(encoding="utf-8")) if args.users else {}
        export = json.loads(Path(args.export).read_text(encoding="utf-8"))
        Path(args.out).write_text(
            json.dumps(convert_mattermost(export, args.channel, users), indent=2), encoding="utf-8"
        )
        return 0
    specs = [
        ModelSpec("llama", m, threads=args.cpu_threads, context=args.context) for m in args.model
    ]
    if args.stub:
        specs.append(ModelSpec("stub", args.stub))
    if not specs:
        parser.error("give at least one --model (or --stub)")
    return _run(args, specs)


if __name__ == "__main__":
    sys.exit(main())
