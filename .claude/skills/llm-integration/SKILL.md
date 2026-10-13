---
name: llm-integration
description: Calling a Large Language Model safely. Use when integrating or changing an LLM call. Covers the server-side key, streamed requests with pause_turn continuation bounded to six resumes, prompt caching, tolerant JSON parsing with one retry then fail-closed, usage and cost accounting against a hard cap, and treating model output as untrusted. Server archetype only; remove this skill if the project has no LLM call.
---

# LLM integration

## Purpose and scope

How a server app calls a Large Language Model (LLM) for a long task: a streamed request with pause-turn continuation, prompt caching, tolerant output parsing with one retry, usage and cost accounting, a hard cost cap, and treating the model's output as untrusted input. Scope is the LLM call and its result handling. It does not cover the HTTP job wrapper (`api-and-integration`) or the store the result merges into (`data-layer`). This applies to the server archetype only; if your project has no LLM call, remove this skill from the bundle for that project. The static archetype never calls an LLM from the shipped artifact (any such tool is local-only, never shipped).

## When to use

- Adding or changing a call to an LLM provider, especially a long or tool-using one.

## Prerequisites

- The provider software development kit (SDK) as an exact-pinned dependency; an API key via the environment (`security-hardening`).
- The call runs inside a background job (`api-and-integration`), never a synchronous request.

## Procedure

1. **Read the key server-side at call time, fail closed if absent.** Never embed it client-side.
2. **Stream the request and handle pause-turn.** A long, tool-using turn can pause; resume by echoing the assistant content back, bounded to six resumes so it can never loop forever.
   ```js
   for (let attempt = 0; attempt < 6; attempt++) {
     const stream = client.messages.stream({ model /*, tools, system, messages */ });
     const message = await stream.finalMessage();
     addUsage(usageAcc, message.usage);
     if (message.stop_reason !== "pause_turn") return message;
     convo = convo.concat([{ role: "assistant", content: message.content }]);
   }
   throw new Error("did not complete after the continuation limit");
   ```
3. **Cache the stable system prefix.** Mark the large, unchanging system block for prompt caching so repeated runs are cheaper; vary only the per-run focus.
4. **Parse the reply tolerantly, then validate.** Strip code fences, take the outermost braces, and parse; on failure retry once asking for JSON only, then fail closed. Pass the parsed object through the boundary validator (`data-layer`) before storing, because model output is untrusted.
   ```js
   function parseJson(text) {
     let t = text.replaceAll(/```json/gi, "").replaceAll("```", "").trim();
     const a = t.indexOf("{"), b = t.lastIndexOf("}");
     if (a >= 0 && b > a) t = t.slice(a, b + 1);
     return JSON.parse(t);   // throws (fail closed) on junk
   }
   ```
5. **Account usage and cap cost.** Accumulate input, output, and cache tokens and any tool or search count across all turns; scale the work budget with the request but clamp it to a hard env-set cap so cost cannot run away. Write one structured audit line per run (`observability-and-audit`). Derive the estimate and the live accounting from ONE price source, so the quote a user sees and the cost actually billed cannot drift. Price each tool by its real billing: a web-search request is charged per request, but a web-fetch has no per-request fee (token cost only), so do not bill a phantom per-fetch charge. And remember server-hosted tools (web search, web fetch) run on the provider's side, not in your container, so you cannot cache or intercept their fetches client-side; design any dedupe or "read a source once" saving into the PROMPT and the scan decomposition, not a local fetch cache that can never exist. If cost pressure tempts a smaller model, confine it to a pass that does not decide or write anything (a pure prose-extraction or reformatting step) and keep discovery, grading, and every write on the capable model: a cheaper model on a non-writing pass is a safe saving, but on a decision or a write it is a silent quality regression the budget hides.
6. **Never invent data.** The prompt instructs the model to mark unverifiable fields with one explicit "unknown" marker and to provide a real source for each record; the validator rejects results that break these rules.

## Decision rules

- **Retry or fail?** One JSON retry, then fail closed. Do not loop on parse failure.
- **Continuation bound?** A fixed maximum of six pause-turn resumes; exceeding it is an error, not an infinite wait.
- **Budget?** Scale searches and tokens with the request's scope and tier, but never above the hard cap.
- **Trust?** Treat every field of the model's output as untrusted; validate before storing, exactly as for a remote user body.

## Standards (checkable assertions)

- The key is read server-side at call time and never reaches the client or a log.
- The streaming loop is bounded to six resumes and handles pause_turn by echoing assistant content.
- Output is parsed tolerantly with exactly one retry, then fails closed; the parsed object is validated at the boundary before storage.
- Token and tool usage is accumulated across turns and an approximate cost is recorded per run.
- The work budget is clamped to a hard env cap.

## Failure modes and remedies

- **The model returns prose around the JSON.** Fix: `parseJson` strips fences and takes the outermost braces; the one retry asks for JSON only, then it fails closed.
- **A tool-using turn never finishes.** Fix: the continuation bound throws after six; raise the limit deliberately only if justified.
- **Cost spikes.** Fix: lower the hard cap env var; confirm the per-run audit line shows the search and token count.
- **Model output contains an invalid record.** Fix: the boundary validator rejects it; the whole run fails closed rather than storing bad data.

## Verification

`npm test` covers the pure helpers (budget scaling, reply parsing of fences, prose, and junk, usage accounting). A live call cannot run in CI without a key and is exercised manually; state this as an unverified-in-CI step where relevant.

## Worked example

A deep run streams; the provider pauses twice for server-side search and is resumed each time; usage accumulates to roughly 30k tokens and 40 searches (under the cap). The reply arrives wrapped in a json fence; `parseJson` strips it and parses. The parsed object passes the boundary validator, then merges as an anti-shrink superset. One audit line records actor, tokens, searches, and an estimated cost.

## Deep in-app scans

A single safe call is the unit here. When the feature is an exhaustive, in-app "update scan" or "find everything" that researches the open web, the same call mechanics compose into a bigger pattern: a server-hosted web-search tool with a per-run cap, a pause-turn continuation limit derived from that search budget, a high output ceiling for a large result, and a multi-pass fan-out. That composition, with its decomposition prompt, fail-closed contract, and superset merge, is `ai-update-scan`.

## Glossary

- **pause_turn:** an LLM streaming signal that the model paused mid-turn (for example to run a server-side tool) and the request must be resumed.
- **Prompt caching:** reusing a cached stable prefix of an LLM request across calls to cut input-token cost.
- **Fail closed:** on a parse or validation failure, reject rather than guess.
- Other terms: `glossary`.

## Provenance

Distilled from the server bundle's scan module, prompt module, and scan tests: the bounded pause-turn loop, prompt caching, tolerant parse with one retry, usage and cost accounting against a hard cap, and the untrusted-output rule.
