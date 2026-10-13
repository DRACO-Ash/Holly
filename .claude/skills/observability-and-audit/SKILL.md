---
name: observability-and-audit
description: Health, logging, and audit. Use when adding logging, a health endpoint, or an audit trail. Covers the static no-telemetry plus human audit row and version stamp, and the server unauthenticated health and readiness paths returning 200, a structured one-line JSON audit per privileged action with a sanitised capped actor, generic client errors with detail server-side, and the rollback and backup signal. No secret in any log.
---

# Observability and audit

## Purpose and scope

What the application exposes for health and what it records. The static artifact carries no runtime telemetry; instead each change adds a human audit row and a version stamp inside the artifact. The server app exposes unauthenticated health and readiness paths that return 200 without leaking secrets, writes one structured JSON audit line per privileged action, returns generic client errors with detail kept server-side, and signals rollbackability. No secret ever appears in any log, audit line, health response, or client error. Scope is health and the audit trail. It does not cover the deploy health gate (`release-and-deploy`).

## When to use

- Adding logging, a health or readiness endpoint, or an audit record.
- Deciding what an error response or health endpoint may reveal.
- Recording a change in the static artifact.

## Prerequisites

- Server: `api-and-integration`, `security-hardening`. Static: `code-architecture`.

## Procedure (static: human audit, no telemetry)

1. **Add no runtime telemetry.** The artifact is offline; it phones nobody.
2. **Record each change as a human audit row** inside the artifact (what changed, why, how verified) and bump the version stamp. This is the audit trail in place of runtime logs.

## Procedure (server: health, audit, errors)

1. **Expose trivial LIVENESS paths returning 200**, unauthenticated and dependency-free, on every conventional path (`/livez`, `/ping`, and a plain `/health`). Liveness must never depend on a downstream, or a transient outage restarts a healthy container. READINESS (`/readyz`, and `/healthz` where it gates traffic) is different: it may report a dependency and return 503 when the app is up but not yet serving (see the storage note below).
   ```js
   app.get(["/healthz","/health","/readyz","/livez","/ping"],
     (req,res)=>res.status(200).type("text/plain").send("ok"));
   ```
   When readiness depends on persistent storage, prove it with a real WRITE, never an existence check: `mkdir` on an existing directory succeeds without write permission, so a root-owned or read-only mount passes an existence check and fails the first real write (the App Store's non-root container against a root-owned volume add-on returns `EACCES` until `securityContext.fsGroup` is set). Race the probe against a hard TIMEOUT strictly shorter than the platform's probe timeout, converting every rejection to a value, so a stalled mount cannot hang the probe forever and be killed silently. On failure return 503 with the resolved data dir and the exact errno in the body (a generic message to the browser, the diagnostic detail here is operational, not a leak), and render it in the client's failure banner (escaped at the sink) so a screenshot is a complete diagnosis. Emit one decisive boot log line recording whether storage accepted a write, and log ready and unready transitions, so a pod the platform kills still leaves a narrative rather than a single "listening" line (`appstore-gate-compliance`).
2. **Expose a status endpoint that reports booleans, never secrets.** Counts and `hasApiKey: true` are fine; the key or any secret is never returned. Build this read-out on the FIRST backend commit, not the first time a deploy misbehaves, and put every field that could answer a plausible failure into it at once rather than adding one per deploy cycle: the build id, each critical config input as a boolean AND a length (never the value, so a stale value and a correct value are distinguishable without leaking either), volume writability (the errno only), the resolved identity (its own identity only, so a missing single-sign-on header is visible), and downstream readiness. In one project this single read-out ended days of blind deploy cycles the moment it existed, because the problem was never hard, only unobservable; a boolean and a length answer in one glance what a deploy cycle would otherwise be spent guessing.
3. **Write one structured JSON audit line per privileged action**: actor, timestamps, before and after counts, and any cost or usage. No secret in the line.
   ```js
   console.log(JSON.stringify({ event:"scan", actor, startedAt, finishedAt,
     searches: usage.web_search_requests||0, inputTokens: usage.input_tokens||0, estimatedCostUsd }));
   ```
4. **Sanitise any user-supplied portion of a log field and bound its length**, to prevent log injection and unbounded growth.
5. **Return generic client errors; keep detail server-side.** Log the full error with `console.error`; return a short `{ error }` with no stack trace.
6. **Classify a failure handler by who initiated the action.** An action the operator explicitly confirmed (a restore, a destructive delete) must surface its failure to that operator as a visible error (a toast or banner), never to `console.debug` alone; only best-effort background work (an audit ping, a cache cleanup) may log quietly. A compliance sweep that adds `.catch` handlers defaulting to `console.debug` silently degrades the product on the exact actions the user cares most about, the user clicked "yes", it failed, the interface said nothing, while making a static-analysis gate green (`appstore-gate-compliance`).
7. **Signal rollbackability.** A destructive write logs that a pre-mutation backup was taken (`data-layer`); the deploy gate checks a tested rollback exists (`release-and-deploy`).

## Procedure (server: signals, SLOs, tracing, alerting)

1. **Measure the four golden signals.** Latency as a distribution (p50, p95, p99) with success and error latency separated; traffic (requests per second); errors (explicit, implicit, and by policy); and saturation (the most constrained resource, held below a utilisation ceiling). Use RED (rate, errors, duration) per request-serving service and USE (utilisation, saturation, errors) per underlying resource.
2. **Define an SLI and an SLO with an error budget.** State an SLI as good events over valid events (for example successful requests over total); set an SLO over a window (for example 99.9% over 28 days), tight enough to keep users happy and no tighter; treat one minus the SLO as the error budget. Agree an error-budget policy: when the budget is healthy, ship; when it is spent, freeze risky releases and spend the effort on reliability.
3. **Propagate a trace.** Instrument with OpenTelemetry and carry the W3C Trace Context (`traceparent`) across every service boundary, so one request is one trace of spans; put the same trace id on every structured log line so logs, traces, and metrics correlate.
4. **Alert on symptoms and burn rate, not causes.** Page on SLO burn (multi-window, multi-burn-rate: a fast burn pages, a slow burn raises a ticket) and on user-visible symptoms, not on raw CPU or disk. Every page is urgent, actionable, and novel, and links a runbook; everything else is a dashboard or a ticket.
5. **Separate the probes.** Liveness is cheap and dependency-free and restarts the container on failure; readiness checks dependencies and only de-registers from the load balancer; a startup probe covers slow boot. Keep every probe path unauthenticated, fast, secret-free, and returning 200.

## Decision rules

- **What may a response or health reveal?** Booleans and counts, never secret values. If unsure, expose a boolean.
- **Audit or nothing?** Any action that spends money, mutates shared state, or deploys gets an audit line (server) or a row (static); pure reads do not.
- **Client message vs server log?** The client gets a generic message; the cause is logged server-side.
- **Static change?** Add the audit row and bump the version stamp in the same change.
- **What do I alert on?** A user-visible symptom or an SLO burn, never a raw resource number; if a page is not worth waking someone, make it a ticket.
- **Liveness or readiness?** Liveness restarts and must not check downstreams; readiness gates traffic and checks them.
- **A deploy misbehaved?** First open the diagnostics read-out and match the symptom, never guess and redeploy; a deploy cycle spent on a question a boolean could answer is the most expensive way to learn nothing. If the read-out lacks the field that would answer it, that is the gap to close, once, with every plausible field at once.

## A figure is checkable when each unit of it names a referent

A register of what a project has verified is worth exactly what a reader can check. One such register
(`docs/AUDIT.md` in this baseline) was corrected in every review round that touched it, almost always
for a COUNT: "22 committed cases" and "three-case table" both stood in that file; nearby files carried
the same defect in the same week, "eight rounds" in `docs/retrospectives/code-with-bob-v2.117-v2.125.md`
and in the in-app change log, which is itself a shipped file. One that went stale in a shipping SCRIPT was "eleven of twelve"
spellings, in `scripts/deployability-check.sh`, added at V2.130 (`git log --all -S"eleven of twelve"`
-> `0e2fc58`) and wrong by the next release. Each was written honestly and each went stale within two
releases, twice against the very command printed beside it.

The remedy for the last of them is the shape to copy, and it arrived in the SAME COMMIT that retired
the figure (`f58bb4d`, V2.131): `test/client-gate.test.mjs` extracts the rule from the shipping script
between markers, drives it over the fixtures, and prints the count when it runs, so the register quotes
a command instead of a number.

**This paragraph took four attempts to cite its own examples, which is the rule proving itself, and the
sequence is the lesson.** Version one said "a retrospective" and "a test's printed output", naming
categories rather than files. Version two moved a unit to `docs/AUDIT.md` on the reasoning that a
register is where such figures live; it was never there, and `git log --all -S"six of thirteen" --
docs/AUDIT.md` returns nothing. Version three named the right file but dated the remedy to V2.140,
when that file has no V2.140 revision at all. Each correction was more specific than the last and
still wrong, because each was reasoned rather than searched. **A correction is an assertion. Run the
same `-S` search behind it that you would demand of the original, and search for the DATE as well as
the file.** A plausible provenance is a fabrication with better manners.

Two remedies, in order of strength:

● **Delete the number and cite the command that produces it.** Prose cannot go stale if it carries no
  figure. Where a count matters, print it from a rung: extract the rule from the shipping script,
  run it over the fixtures, and let the test emit the only number anyone quotes.
● **If you must enumerate, make every element point at something.** Replacing "three-case table" with
  a list of four NAMED cases, each resolving to a real test, is still a count, but a checkable one.
  Naming instead of counting is not honesty by itself: the name has to have a referent a reader can
  follow, or it is the same unchecked figure wearing a different coat.

And the standing rule for every figure anywhere: state the SCOPE of the query beside it. A run list
filtered to one branch, presented as the complete record, produced a claim that was wrong twice over.

## Standards (checkable assertions)

- No secret appears in any log line, audit record, health response, or client error.
- Server: health and readiness paths return 200 unauthenticated and touch nothing.
- Server: a secret-free diagnostics read-out exists from the first backend commit, reporting the build id, each critical input as a boolean and a length (never the value), volume writability (errno only), and identity resolution, with every plausible field present at once.
- Server: every privileged action emits one structured audit line with actor, timings, and cost or usage.
- Server: user-supplied log content is sanitised and length-bounded; client errors are generic.
- Static: each change adds a human audit row and bumps the version stamp; no runtime telemetry exists.
- Server: the four golden signals are measured; at least one user-centric SLO with an error budget is defined; a trace id correlates logs and traces; alerts fire on symptoms or SLO burn, not raw causes; liveness, readiness, and startup probes are distinct.

## Failure modes and remedies

- **A secret appears in a log.** Fix: log a boolean or redacted marker; rotate the secret if it was emitted.
- **A probe fails though the app serves.** Fix: ensure the conventional health paths exist and return 200 and the app listens on the platform's probe port.
- **A stack trace leaks to a client.** Fix: catch and return a generic `{ error }`; log detail server-side.
- **A log field grows unbounded or carries injected newlines.** Fix: sanitise and cap it.

## Verification

Server: `npm test` confirms health and readiness return 200 unauthenticated; triggering a privileged action produces one JSON audit line with no secret. Static: the artifact has a human audit row and an incremented version stamp, and a grep finds no telemetry call.

## Worked example

Server: a scan runs and the app emits one line `{"event":"scan","actor":"web:ada","searches":40,"inputTokens":31000,"estimatedCostUsd":0.71}` with no key and the actor sanitised and capped. `/readyz` returns 200 throughout. A failed dataset read logs the full error server-side but returns `{"error":"could not read the dataset"}` to the client.

## Glossary

- **Health / readiness probe:** an HTTP path the platform calls to decide if a pod is serving; returns 200.
- **Audit line / audit row:** a per-privileged-action record (JSON line on the server, human row in the static artifact); never holds a secret.
- **Log injection:** smuggling newlines through a user field to forge log lines; defended by sanitising and capping.
- **Golden signals / SLI / SLO / error budget:** latency, traffic, errors, saturation; the indicator, its target, and one minus the target.
- **RED / USE:** rate-errors-duration per service; utilisation-saturation-errors per resource.
- **Trace context:** the `traceparent` carried across services so one request is one trace.
- Other terms: `glossary`.

## Provenance

Merged from the static bundle's no-telemetry and human audit row practice and the server bundle's observability skill (unauthenticated health and readiness paths, structured no-secret audit line, sanitised capped actor, generic client errors, rollback and backup signal).
