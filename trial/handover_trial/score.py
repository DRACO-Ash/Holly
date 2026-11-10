"""Scores a model's kept claims against the mission lead's answer key and applies the pass marks.

The answer key is what a mission lead reads in each thread, written down before anyone sees the
model's output: {"thread_id": "...", "claims": [{post_id, provider, quantity, value, unit}]}.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .claims import Claim, Providers, Thread, figure_in_post, parse_claims

BUDGET_S = 300.0


@dataclass(frozen=True)
class Marks:
    """The proposed pass marks. The owner may change any of them before the trial runs."""

    min_recall: float = 0.8
    max_wrong_provider: int = 0
    budget_s: float = BUDGET_S
    min_headroom_gib: float = 1.0


@dataclass(frozen=True)
class Load:
    """What the run has to fit: Holly's own peak memory and a typical shift's thread count, both
    measured or supplied by the owner, never assumed by the harness."""

    limit_gib: float
    holly_peak_gib: float
    shift_threads: int


def load_keys(folder: Path) -> dict[str, list[Claim]]:
    keys: dict[str, list[Claim]] = {}
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        claims, refused = parse_claims(data)
        if refused:
            raise ValueError(f"{path.name}: answer key has malformed claims: {refused}")
        keys[str(data["thread_id"])] = claims
    return keys


def _same_value(a: Claim, b: Claim) -> bool:
    if a.signed and b.signed:
        return a.value == b.value
    return abs(a.value) == abs(b.value)


def _same(a: Claim, b: Claim, providers: Providers, with_provider: bool = True) -> bool:
    same_provider = providers.canonical(a.provider) == providers.canonical(b.provider)
    return (
        a.post_id == b.post_id
        and a.quantity == b.quantity
        and a.unit == b.unit
        and _same_value(a, b)
        and (same_provider or not with_provider)
    )


def _kept(run: dict[str, Any], thread_id: str) -> list[Claim]:
    for t in run["threads"]:
        if t["thread_id"] == thread_id:
            return [
                Claim(
                    c["post_id"], c["provider"], c["quantity"], c["value"], c["unit"], c["signed"]
                )
                for c in t["claims"]
                if c["result"] == "kept"
            ]
    return []


def score(
    run: dict[str, Any],
    threads: list[Thread],
    keys: dict[str, list[Claim]],
    providers: Providers,
    load: Load,
    marks: Marks,
) -> dict[str, Any]:
    key_total = matched = wrong_provider = other_wrong = unsupported = 0
    by_thread = {t.thread_id: t for t in threads}
    for thread_id, key in keys.items():
        kept = _kept(run, thread_id)
        key_total += len(key)
        thread = by_thread.get(thread_id)
        for claim in kept:
            post = thread.post(claim.post_id) if thread else None
            if post is None or not figure_in_post(claim, post):
                unsupported += 1  # cannot happen if the checks hold; counted to prove it
            if any(_same(claim, k, providers) for k in key):
                matched += 1
            elif any(_same(claim, k, providers, with_provider=False) for k in key):
                wrong_provider += 1
            else:
                other_wrong += 1
    kept_total = matched + wrong_provider + other_wrong
    dropped: dict[str, int] = {}
    seconds = []
    for t in run["threads"]:
        seconds.append(t["seconds"])
        for c in t["claims"]:
            if c["result"] != "kept":
                dropped[c["result"]] = dropped.get(c["result"], 0) + 1
    mean_s = sum(seconds) / len(seconds) if seconds else 0.0
    projected_s = run["load_seconds"] + mean_s * load.shift_threads
    peak_gib = run["peak_rss_mib"] / 1024
    headroom = load.limit_gib - load.holly_peak_gib - peak_gib
    recall = matched / key_total if key_total else 0.0
    tests = {
        "no unsupported figure kept": unsupported == 0,
        f"no figure kept under the wrong provider (at most {marks.max_wrong_provider})": wrong_provider
        <= marks.max_wrong_provider,
        f"finds at least {marks.min_recall:.0%} of the lead's claims": recall >= marks.min_recall,
        f"a typical shift ({load.shift_threads} threads) fits in {marks.budget_s:.0f} s": projected_s
        <= marks.budget_s,
        f"leaves at least {marks.min_headroom_gib} GiB of memory spare": headroom
        >= marks.min_headroom_gib,
        "ran without error": not run.get("error"),
    }
    return {
        "model": run["model"],
        "error": run.get("error", ""),
        "key_claims": key_total,
        "kept": kept_total,
        "matched": matched,
        "wrong_provider_kept": wrong_provider,
        "other_wrong_kept": other_wrong,
        "unsupported_kept": unsupported,
        "dropped": dropped,
        "refused_malformed": sum(len(t["refused"]) for t in run["threads"]),
        "unparsed_replies": sum(t["unparsed_replies"] for t in run["threads"]),
        "recall": round(recall, 3),
        "precision": round(matched / kept_total, 3) if kept_total else 0.0,
        "load_s": run["load_seconds"],
        "thread_s": seconds,
        "mean_thread_s": round(mean_s, 2),
        "projected_shift_s": round(projected_s, 1),
        "peak_gib": round(peak_gib, 2),
        "headroom_gib": round(headroom, 2),
        "probe": run.get("probe", {}),
        "tests": tests,
        "go": all(tests.values()),
    }


def report(scores: list[dict[str, Any]], load: Load, marks: Marks, meta: dict[str, str]) -> str:
    lines = [
        "# Handover local-model trial: results",
        "",
        "Generated by trial/handover_trial. Holds post ids and figures only, never thread text.",
        "",
        *(f"- {k}: {v}" for k, v in meta.items()),
        f"- Memory limit {load.limit_gib} GiB, Holly's own peak {load.holly_peak_gib} GiB, "
        f"typical shift {load.shift_threads} threads, budget {marks.budget_s:.0f} s",
        "",
        "| Model | Go | Found | Precision | Wrong provider | Unsupported kept | Load s | Mean s per thread | Shift s | Peak GiB | Spare GiB |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s in scores:
        lines.append(
            f"| {s['model']} | {'GO' if s['go'] else 'NO-GO'} | {s['matched']}/{s['key_claims']} "
            f"({s['recall']:.0%}) | {s['precision']:.0%} | {s['wrong_provider_kept']} | "
            f"{s['unsupported_kept']} | {s['load_s']} | {s['mean_thread_s']} | "
            f"{s['projected_shift_s']} | {s['peak_gib']} | {s['headroom_gib']} |"
        )
    for s in scores:
        lines += ["", f"## {s['model']}", ""]
        if s["error"]:
            lines.append(f"Error: {s['error']}")
        lines += [f"- {'PASS' if ok else 'FAIL'}: {name}" for name, ok in s["tests"].items()]
        probe = s.get("probe") or {}
        if "slowdown" in probe:
            lines.append(
                f"- Responsiveness (reported, not a pass mark): a fixed task took "
                f"{probe['baseline_ms']} ms before the run and {probe['p95_ms']} ms (95th "
                f"percentile) during it, {probe['slowdown']} times slower"
            )
        lines.append(f"- Dropped by the checks: {s['dropped'] or 'none'}")
        lines.append(
            f"- Malformed claims refused: {s['refused_malformed']}; unreadable replies: {s['unparsed_replies']}"
        )
        lines.append(
            f"- Other wrong claims kept (figure and provider right, quantity or unit wrong, or not in the key): {s['other_wrong_kept']}"
        )
    return "\n".join(lines) + "\n"
