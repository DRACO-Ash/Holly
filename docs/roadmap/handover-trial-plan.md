# Handover Phase 0: local-model trial plan

Status: ready to run, not yet run. Prepared on 9 November 2026. Part of the Handover proposal (`docs/roadmap/handover-module.md`, phase 0 item 3); its result decides whether V0.20 ships the built-in model.

## The question the trial answers

Can a language model running on CPU inside an 8Gi, 6 CPU container read a shift's Mattermost threads within 5 minutes and pull out the providers' figures accurately enough to put in a handover, with no made-up figure getting through?

The answer is a go or no-go per candidate model, measured against pass marks agreed in advance, on real threads, inside Bluestaq's environment.

## What is already built

The harness is in `trial/`, outside Holly's upload and outside its verification loop. See `trial/README.md` for the commands.

● **The same checks Holly would ship.** Every figure the model pulls out must pass 3 checks before it counts (`trial/handover_trial/claims.py`):
  ■ the number is written in the post it cites, with any sign the post writes;
  ■ the provider is on the configured list and is either named in the post (or by alias) or is the post author's company;
  ■ the post belongs to the thread.

  The provider check is stricter than the plan's first wording, which asked only that the provider be on the list. A figure is now credited to a provider only when the post itself ties it to that provider.
● **A child process per model, as in Holly.** The model runs in its own process with text in and results out, and the container runs with `--network none`. The harness records load time, time per thread and the child's peak memory.
● **Scoring against a mission lead's answer key**, written before anyone sees model output.
● **A dry run on synthetic data with a stand-in model**, so the whole pipeline can be proved with no real data. Its output, below, shows each check and each score working.
● **17 unit tests**, standard library only. The container build pins the runtime by hash: llama-cpp-python 0.3.36 (MIT licence, released 1 October 2026, past the 15-day cooldown).

## Pass marks (proposed; the owner confirms before the run)

| Mark | Proposed threshold | Why |
|---|---|---|
| Unsupported figures kept | 0 | The checks must hold on real data. The harness counts these independently of the checks. |
| Figures kept under the wrong provider | 0 | The checks cannot catch a figure swapped between two providers named in the same post. Only the answer key catches it, and it is the error that would mislead a handover. |
| Lead's claims found | 80% or more | Below this, the lead would be filling too many gaps by hand. |
| A typical shift fits | 5 minutes or less, load time included | The budget the owner set for the end-of-shift run. |
| Memory spare | 2 GiB or more, after Holly's own peak and the model's | Keeps Holly clear of being stopped for running out of memory. |

**2 inputs come from the owner, not the harness:**
● **Holly's own peak memory.** Read it from the App Store's metrics for the `holly` app (`TBC, re-verify` where the console shows it). Pass it as `--holly-peak-gib`.
● **The number of threads in a typical shift's run.** Count the threads behind the live events of a recent, busy shift. Pass it as `--shift-threads`.

## Candidate models

All are instruction-tuned, permissively licensed and run as 4-bit quantised GGUF files (Q4_K_M) on CPU.

| Model | Size | Licence | Why it is a candidate |
|---|---|---|---|
| Phi-3.5-mini-instruct | 3.8 billion parameters | MIT | The smallest; the fastest if it is accurate enough |
| Qwen2.5-7B-Instruct | 7.6 billion parameters | Apache-2.0 | Strong at structured output |
| Mistral-7B-Instruct-v0.3 | 7.2 billion parameters | Apache-2.0 | A widely used baseline of the same size |

Confirm each licence from the model card when downloading. Record the source and the SHA-256 of every file; the report prints the SHA-256 of each model it runs. The operator may substitute a newer permissively licensed instruct model of 3 to 8 billion parameters, recorded the same way.

## Who does what

| Role | Task | Time (estimate) |
|---|---|---|
| Owner | Confirm the pass marks, supply Holly's peak memory and the typical thread count, decide go or no-go | 1 hour |
| Data owner | Approve exporting real threads to the trial machine inside Bluestaq | Before step 3 |
| Holly engineer (operator) | Build, export, run, report | About 1 day |
| Mission lead | Write the answer keys for the 5 threads, before seeing any model output | 2 to 3 hours |
| Second mission lead | Spot-check one answer key | 30 minutes |

## Steps

1. **Prerequisites.**
   ■ A Bluestaq machine with Docker, at least 6 cores and 12 GiB of memory, so the 8Gi cap is the binding limit.
   ■ The model files downloaded and their SHA-256 recorded.
   ■ The provider list (`providers.json`): names, aliases and the Mattermost display names of authors who speak for each provider.
   ■ The data owner's approval to use real threads on that machine.
2. **Build and self-test the container.**
   ■ Build it.
   ■ Run the unit tests and the dry run inside it.
   ■ The dry run must produce the report shown below.
3. **Choose and export 5 real threads.**
   ■ Cover 5 cases:
     ● a manoeuvre where providers disagreed;
     ● an RPO;
     ● a photometric change;
     ● a separation or other event type;
     ● the longest, noisiest thread of the last month.
   ■ Export each with Mattermost's `GET /api/v4/posts/{root_post_id}/thread` using the operator's own access.
   ■ Convert each with `python -m handover_trial convert`.
   ■ Keep the files on the trial machine only, outside any git repository.
4. **Write the answer keys.**
   ■ The mission lead lists every provider figure in each thread, using the fixed quantities and units, without seeing any model output.
   ■ A second lead spot-checks one key.
5. **Run every candidate model** with the network off and the 8Gi / 6 CPU caps (`trial/README.md`).
6. **Review the report.** For any wrong claim kept, read the post and record why. This shapes the prompt and the checks for V0.20.
7. **Decide.**
   ■ Choose the smallest model that passes every mark. If 2 pass, prefer the higher recall, then the lower memory.
   ■ If none passes, the owner chooses:
     ● ship V0.20 with the template synopsis only, and keep the model out;
     ● change a pass mark, recorded as a decision;
     ● trial again with other models.
8. **Record and clean up.**
   ■ Commit a short results note: models, pass or fail per mark, timings and memory. It must contain no thread text and no figures from real posts.
   ■ Feed the note into ADR-016.
   ■ Delete the exported threads and keys from the trial machine.

## Data handling

● Real threads, answer keys and run outputs stay on the trial machine inside Bluestaq. None is committed, uploaded or pasted into any outside tool, including an AI assistant.
● The container has no network while a model runs, and the data folder is mounted read-only.
● Run outputs hold post ids and figures, not thread text. They are still operational data: they stay on the machine and are deleted at step 8.

## Dry-run result (synthetic data, stand-in model)

This proves the pipeline end to end. The stand-in replies were built to break every rule once:
● a made-up figure, dropped by the figure check;
● a provider not on the list, dropped by the provider check;
● a post outside the thread, dropped by the thread check;
● a malformed claim, refused before the checks;
● a claim missed, which lowers recall;
● a figure swapped between two providers named in the same post. The checks keep it, and the answer key catches it.

| Model | Go | Found | Precision | Wrong provider | Unsupported kept |
|---|---|---|---|---|---|
| stub (synthetic) | NO-GO | 7/10 (70%) | 88% | 1 | 0 |

It fails on wrong provider and on recall, as designed.

## Limits of the trial

● **5 threads is a small sample.** It can show that a model fails; it cannot prove that one never errs. The checks and the lead's confirmation stay in V0.20 whatever the result.
● **Scope.** The trial measures extraction only, not the wording of a synopsis.
● **Different hardware.** Timings on the trial machine are a guide to the App Store's, not the same thing. V0.20 measures the run in Holly itself, and its audit row records the real time.
