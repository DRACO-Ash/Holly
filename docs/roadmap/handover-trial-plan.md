# Handover Phase 0: local-model trial plan

Status: ready to run, not yet run. Prepared on 9 November 2026; revised on 10 November 2026 for Holly's fixed allocation. Part of the Handover proposal (`docs/roadmap/handover-module.md`, phase 0 item 3); its result decides whether V0.20 ships the built-in model. The step-by-step operator guide is `docs/roadmap/handover-trial-guide.md`.

## What changed on 10 November 2026

The owner confirmed that Holly cannot have more than its current allocation: **4Gi memory and 2000m CPU (2 CPUs)**. The earlier plan assumed a rise to 8Gi and 6 CPUs, so the trial now differs in 5 ways:

● **The model and Holly share 4 GiB.** Holly's web app, background loops and the model's child process must all fit, so the model must be small. The candidates are now models of about 0.5 to 2 billion parameters, with one larger model kept as a stretch test.
● **The model and Holly share 2 CPUs.** The child process runs at the lowest priority, so Holly's own work comes first. The trial now also reports how much slower a small fixed task runs while the model works. That figure stands in for how sluggish Holly's pages would feel during the run.
● **The memory mark is now 1 GiB spare, down from 2 GiB (proposed; owner to confirm).** With 4 GiB in total, a 2 GiB margin would leave too little room for any model. The model's memory is freed when the run ends, so the margin only has to hold for those few minutes.
● **The trial container runs with `--memory 4g --cpus 2`,** and the harness defaults to 2 CPU threads and a 4,096-token window.
● **Small models are less accurate, which raises the chance of a no-go.** The fallback is unchanged: V0.20 ships the template synopsis without the model. One more option is now on the table: reading threads in short, low-priority slots through the shift instead of all in the last 5 minutes. That is the owner's call.

## The question the trial answers

Can a small language model, sharing Holly's 4 GiB and 2 CPUs, read a shift's Mattermost threads within 5 minutes and pull out the providers' figures accurately enough to put in a handover, with no made-up figure getting through and without making Holly unusable while it runs?

The answer is a go or no-go per candidate model, measured against pass marks agreed in advance, on real threads, inside Bluestaq's environment.

## What is already built

The harness is in `trial/`, outside Holly's upload and outside its verification loop.

● **The same checks Holly would ship.** A figure counts only when all 3 hold:
  ■ the number is written in the post it cites, with any sign the post writes;
  ■ the post ties it to a provider on the configured list, by naming the provider or an alias, or because its author speaks for that provider;
  ■ the post belongs to the thread.
● **A child process per model, as in Holly.** The model gets text in and hands results back, at the lowest priority, with the container's network switched off. The harness records:
  ■ load time;
  ■ time per thread;
  ■ the child's peak memory;
  ■ a responsiveness probe: how much slower a fixed task runs at normal priority during the run.
● **Scoring against a mission lead's answer key**, written before anyone sees model output.
● **A dry run on synthetic data with a stand-in model**, which shows every check and score working.
● **20 unit tests**, standard library only, including the no-container route against a stand-in server.
● **A container whose runtime is pinned by hash:** llama-cpp-python 0.3.36, MIT licence, released 1 October 2026, past the 15-day cooldown. It is built in this sandbox and passes its tests and dry run with the network off.

## Pass marks (proposed; the owner confirms before the run)

| Mark | Proposed threshold | Why |
|---|---|---|
| Unsupported figures kept | 0 | The checks must hold on real data. The harness counts these independently. |
| Figures kept under the wrong provider | 0 | The checks cannot catch a figure swapped between two providers named in the same post. Only the answer key catches it, and it is the error that would mislead a handover. |
| Lead's claims found | 80% or more | Below this, the lead fills too many gaps by hand. |
| A typical shift fits | 5 minutes or less, load time included | The budget the owner set for the end-of-shift run. |
| Memory spare | 1 GiB or more, after Holly's own peak and the model's | Keeps Holly clear of being stopped for running out of memory. Changed from 2 GiB; see above. |

Reported but not a pass mark: the responsiveness slowdown. The owner may turn it into a mark, for example "no more than 3 times slower", once the first numbers are in.

**2 inputs come from the owner, not the harness:**
● **Holly's own peak memory.** Read it from the App Store's metrics for the `holly` app (`TBC, re-verify` where the console shows it). Pass it as `--holly-peak-gib`. It decides how much of the 4 GiB is left for the model.
● **The number of threads in a typical shift's run.** Count the threads behind the live events of a recent, busy shift. Pass it as `--shift-threads`.

## Candidate models

All are instruction-tuned, permissively licensed and run as 4-bit quantised GGUF files (Q4_K_M) on the CPU alone. The sizes are approximate.

| Model | Size | Licence | File (about) | Why it is a candidate |
|---|---|---|---|---|
| Qwen2.5-1.5B-Instruct | 1.5 billion parameters | Apache-2.0 | 1 GB | The best balance of size and structured output among the small models |
| SmolLM2-1.7B-Instruct | 1.7 billion parameters | Apache-2.0 | 1 GB | A second small model, from another builder |
| Qwen2.5-0.5B-Instruct | 0.5 billion parameters | Apache-2.0 | 0.4 GB | The floor: the fastest and leanest, if it is accurate enough |
| Phi-3.5-mini-instruct (stretch) | 3.8 billion parameters | MIT | 2.4 GB | Expected to break the memory mark; run once to see how far off it is |

Confirm each licence from the model card when downloading. Avoid models under use-restricted licences, such as the Qwen2.5 3B research licence or the Llama community licence. Record the source and the SHA-256 of every file; the report prints the SHA-256 of each model it runs. The operator may substitute a newer permissively licensed instruct model of up to 2 billion parameters, recorded the same way.

## Who does what

| Role | Task | Time (estimate) |
|---|---|---|
| Owner | Confirm the pass marks, supply Holly's peak memory and the typical thread count, decide go or no-go | 1 hour |
| Data owner | Approve exporting real threads to the trial machine inside Bluestaq | Before step 3 |
| Holly engineer (operator) | Build, export, run, report | About 1 day |
| Mission lead | Write the answer keys for the 5 threads, before seeing any model output | 2 to 3 hours |
| Second mission lead | Spot-check one answer key | 30 minutes |

## Steps

The full how-to for each step is in `docs/roadmap/handover-trial-guide.md`.

1. **Prerequisites.**
   ■ A Bluestaq computer approved for the data, with at least 2 CPU cores and 8 GB of memory. Either route works:
     ● Route A: a Windows laptop with no container, using Python installed for the user only and llama.cpp's ready-built `llama-server.exe`;
     ● Route B: a machine with Docker or Podman.
   ■ The model files downloaded and their SHA-256 recorded.
   ■ The provider list.
   ■ The data owner's approval.
2. **Build and self-test the container.** The unit tests and the dry run must pass.
3. **Choose and export 5 real threads.**
   ■ Cover 5 kinds:
     ● a manoeuvre where providers disagreed;
     ● an RPO;
     ● a photometric change;
     ● a separation or other event type;
     ● the longest, noisiest thread of the last month.
   ■ Export each from Mattermost and convert it.
   ■ Keep the files on the trial machine only, outside any git repository.
4. **Write the answer keys.** The mission lead does this without seeing model output, and a second lead spot-checks one.
5. **Run every candidate** with Holly's settings: 2 CPU threads, a 4,096-token window and low priority.
   ■ Route B enforces the 4 GiB cap and switches the network off.
   ■ Route A binds the model to the laptop only (127.0.0.1) and scores the measured peak memory against the 4 GiB instead of enforcing it.
6. **Review the report.** For any wrong claim kept, read the post and record why.
7. **Decide.**
   ■ Choose the smallest model that passes every mark. If 2 pass, prefer the higher recall, then the lower memory.
   ■ If none passes, the owner chooses:
     ● ship V0.20 with the template synopsis only;
     ● read threads in low-priority slots through the shift, so the end-of-shift run only reads what is new, then re-run the trial on that basis;
     ● change a pass mark, recorded as a decision;
     ● trial other models.
8. **Record and clean up.**
   ■ Commit a short results note with no thread text and no real figures.
   ■ Feed it into ADR-016.
   ■ Delete the exported threads and keys.

## Data handling

● Real threads, answer keys and run outputs stay on the trial machine inside Bluestaq. None is committed, uploaded or pasted into any outside tool, including an AI assistant.
● The container has no network while a model runs, and the data folder is mounted read-only.
● Run outputs hold post ids and figures, not thread text. They are still operational data: they stay on the machine and are deleted at step 8.

## Dry-run result (synthetic data, stand-in model)

| Model | Go | Found | Precision | Wrong provider | Unsupported kept |
|---|---|---|---|---|---|
| stub (synthetic) | NO-GO | 7/10 (70%) | 88% | 1 | 0 |

The stand-in replies break every rule once, and each break is caught:
● a made-up figure, dropped;
● a provider not on the list, dropped;
● a post outside the thread, dropped;
● a malformed claim, refused;
● a missed claim, which lowers recall;
● a figure swapped between two providers in one post, which the checks keep and only the answer key catches.

## Limits of the trial

● **5 threads is a small sample.** It can show that a model fails; it cannot prove that one never errs. The checks and the lead's confirmation stay in V0.20 whatever the result.
● **Scope.** It measures extraction, not the wording of a synopsis.
● **Not the real Holly.** The trial machine is not Holly's App Store node, and Holly's own load is not running beside the model; the responsiveness probe is a stand-in for it. V0.20 measures the real run in Holly, and its audit row records the time.
