# Handover trial: a step-by-step guide for first-timers

Bluestaq Limited · Holly · 10 November 2026

This guide walks you through running the Handover local-model trial from start to finish, assuming you have never done anything like it before. The trial plan (`docs/roadmap/handover-trial-plan.md`) says **why** and **what passes**; this guide says **how**.

## 1. What the trial is, in one minute

Holly's planned Handover tab will use a small language model, running inside Holly, to read Mattermost threads near the end of each shift and pull out what each provider said (for example "NorthStar: +25 s period change"). Before building that into Holly, we test whether a small model can do the job well enough on Holly's fixed allocation of **4 GB of memory and 2 CPUs**.

The trial runs a few candidate models over 5 real threads and compares what each one finds with what a mission lead found by hand. It then gives each model a plain **GO** or **NO-GO**.

**What the trial is not:**
● It is not part of the Holly app and is not uploaded to the App Store.
● It does not touch the live Holly app, its database or its settings.
● It does not send anything outside Bluestaq: the model runs with the network switched off.

## 2. What it changes in Holly: nothing

The trial's files live in Holly's code repository, in the `trial/` folder and in three documents under `docs/roadmap/`. Being in the repository does not make them part of Holly.

| Area | Effect of the trial | Why |
|---|---|---|
| The Holly app on the App Store | None | The trial runs on a separate machine. It never connects to Holly. |
| Holly's upload package | None | The packaging script lists exactly which files go into an upload (`PATHS` in `scripts/package-appstore.sh`). `trial/` is not on that list, so it can never be uploaded. |
| The App Store pipeline and code quality scan | None | They only see the upload package, which does not contain `trial/`. |
| Holly's verification loop and tests | None | The loop checks `src/`, `tests/` and `frontend/` only. |
| Holly's version number | None | Only changes to the upload bump the version. |
| Holly's database, settings and users | None | The trial reads exported copies of threads, never Holly. |
| The repository | Adds `trial/` and 3 documents | Real data can never be committed: `trial/.gitignore` blocks the data and output folders, and this guide keeps them outside the repository anyway. |

The trial's own image (its "container") is separate from Holly's. Building or deleting it does nothing to Holly.

## 3. Before you start: the checklist

Tick every item before step 5. The first 4 are decisions or inputs from other people.

| # | Item | From whom |
|---|---|---|
| 1 | The pass marks confirmed (see the trial plan) | Owner |
| 2 | Holly's own peak memory, read from the App Store metrics for the `holly` app | Owner or platform team |
| 3 | How many threads a typical shift's run would read | Owner, with a mission lead |
| 4 | Approval to copy 5 real Mattermost threads onto the trial machine | Data owner |
| 5 | A trial machine (section 4) | You |
| 6 | A mission lead booked for 2 to 3 hours to write the answer keys | Owner |
| 7 | The model files (section 7) | You |

## 4. What you need

### The trial machine

Any Bluestaq-managed computer that is approved for the data and can run Docker:

● **Processor:** 2 CPU cores or more. The trial limits itself to 2 so it matches Holly.
● **Memory:** 8 GB or more. The trial limits itself to 4 GB; the rest keeps the machine itself comfortable.
● **Disk:** 15 GB free, for the image of about 2 GB, the models of up to about 5 GB and the outputs.
● **Operating system:** Linux is simplest. Windows or macOS work with Docker Desktop (see the note below).
● **Network:** internet access to PyPI (`pypi.org`) while you **build** the image, and to wherever you download the models from. Running the trial needs no network at all. If the machine has no internet at all, see section 11.

**If you use Docker Desktop on Windows or macOS:** open Docker Desktop's Settings, then Resources, and give it at least 6 GB of memory and 2 CPUs. If you don't, the trial's 4 GB limit cannot be honoured.

### Software

● **Git**, to fetch the code.
● **Docker** (Docker Engine on Linux, Docker Desktop on Windows or macOS).
● Optional: **Python 3.12**. It is only needed if you want to run the self-tests outside Docker or convert threads on a machine without Docker.

### Access

● Read access to the `draco-ash/holly` repository on GitHub.
● A way to export Mattermost threads: your own Mattermost personal access token, or a Mattermost administrator who can export them for you. Whether personal tokens are switched on for Bluestaq's Mattermost is `TBC, re-verify` with its administrator.

## 5. Where to put everything

Make one working folder on the trial machine, **outside** any git repository, for example `~/handover-trial` on Linux or `C:\handover-trial` on Windows. Inside it:

```
handover-trial/
  holly/                 the code (step 6.1); you never put data in here
  trial-data/            everything real; read-only to the trial
    providers.json       the provider list
    users.json           Mattermost user ids to names (step 8)
    raw/                 the threads as exported from Mattermost
    threads/             the threads converted for the trial
    keys/                the mission lead's answer keys
    models/              the model files
  trial-out/             the results
```

Keeping real data outside the `holly/` folder means it cannot be committed by accident.

## 6. Build the trial and check it works

### 6.1 Get the code

```
cd ~/handover-trial
git clone https://github.com/draco-ash/holly.git
cd holly
git checkout claude/rehydrate-foundations-bundle-abogpu
```

Once this work is merged, use the main branch instead.

### 6.2 Build the image

```
docker build -t holly-handover-trial trial/
```

This compiles the model runtime from source, so it takes several minutes. It ends with a line that says the image was named `holly-handover-trial`. The build only downloads from PyPI, and every download is checked against a fingerprint (hash) pinned in `trial/requirements-trial.txt`. A download that doesn't match stops the build.

### 6.3 Run the self-tests

```
docker run --rm --network none --entrypoint python holly-handover-trial -m unittest discover -s tests
```

You should see `OK` at the end.

### 6.4 Run the dry run

The dry run uses made-up threads and a stand-in for the model, so it needs no real data.

Linux or macOS:
```
mkdir -p ~/handover-trial/trial-out && chmod 777 ~/handover-trial/trial-out
docker run --rm --network none --memory 4g --memory-swap 4g --cpus 2 \
  -v ~/handover-trial/trial-out:/out holly-handover-trial dry-run --out /out/dry
```

Windows PowerShell (the line-continuation `\` becomes a backtick, and paths use `C:\`):
```
docker run --rm --network none --memory 4g --memory-swap 4g --cpus 2 `
  -v C:\handover-trial\trial-out:/out holly-handover-trial dry-run --out /out/dry
```

The report ends with **NO-GO**. That is correct: the stand-in was built to make mistakes, and the report shows each one being caught. The table row reads `7/10 (70%)`, with `1` under Wrong provider and `0` under Unsupported kept.

## 7. Get the models

1. Download the GGUF file, in its `Q4_K_M` version, for each candidate in the trial plan's table, from a source your team trusts.
2. **Check the licence** on each model's page. It must be MIT or Apache-2.0. Write it down.
3. **Record each file's fingerprint (SHA-256):**
   ■ Linux: `sha256sum file.gguf`
   ■ macOS: `shasum -a 256 file.gguf`
   ■ Windows PowerShell: `Get-FileHash file.gguf`
4. Put the files in `trial-data/models/`.

The report also prints each model's fingerprint, so you can confirm the file you ran is the file you recorded.

## 8. Get the threads

### 8.1 Choose 5

Pick, with a mission lead, one thread of each kind:
● a manoeuvre where providers disagreed;
● an RPO;
● a photometric change;
● a separation or other event type;
● the longest, noisiest thread of the last month.

### 8.2 Find each thread's id

In Mattermost, open the first post of the thread, choose **Copy Link**, and paste it somewhere. The id is the last part of the link, after `/pl/`.

### 8.3 Export it

Keep your token out of files and out of your command history by putting it in a variable first. In each command below, replace `<mattermost-host>` with your Mattermost address and `<id>` with the thread id.

Linux or macOS:
```
read -s MM_TOKEN    # paste the token, press Enter; nothing is shown
curl -sS -H "Authorization: Bearer $MM_TOKEN" \
  https://<mattermost-host>/api/v4/posts/<id>/thread -o ~/handover-trial/trial-data/raw/<id>.json
```

Then fetch the names of everyone who posted, so the trial can tell which analyst speaks for which provider. List their user ids from the export (each post has a `user_id`) and run:

```
curl -sS -X POST -H "Authorization: Bearer $MM_TOKEN" -H "Content-Type: application/json" \
  -d '["<user id 1>","<user id 2>"]' \
  https://<mattermost-host>/api/v4/users/ids -o ~/handover-trial/trial-data/users.json
```

Close the terminal when you are done so the token is forgotten.

### 8.4 Convert it

```
cd ~/handover-trial
docker run --rm --network none -v "$PWD/trial-data:/data" holly-handover-trial \
  convert --export /data/raw/<id>.json --channel <channel name> --users /data/users.json \
          --out /data/threads/<id>.json
```

This is the only command that writes to `trial-data`. Every other command reads it as read-only. If it reports `Permission denied`, make `trial-data/threads` writable the same way as `trial-out` (section 13).

## 9. Write the provider list and the answer keys

### 9.1 The provider list

Create `trial-data/providers.json`. List each provider with any other names it goes by, and map each Mattermost username that posts on a provider's behalf to that provider:

```
{
  "providers": {
    "NorthStar": {"aliases": ["North Star"]},
    "KBR": {"aliases": []}
  },
  "authors": {
    "<mattermost username>": "NorthStar"
  }
}
```

Only the owner decides which providers go on the list. Don't guess.

### 9.2 The answer keys

The mission lead writes one file per thread in `trial-data/keys/`, **before seeing any model output**. It lists every figure a provider gave in that thread:

```
{"thread_id": "<thread id>",
 "claims": [
   {"post_id": "<post id>", "provider": "NorthStar", "quantity": "period_change", "value": "+25", "unit": "s"}
 ]}
```

The rules for the lead:
● Include a figure only if the post ties it to a provider: it names the provider, or the author speaks for one.
● Copy the number as written. Add a sign only if the post writes one.
● Use only these quantities and units:
  ■ `period_change` (s or min)
  ■ `apogee_change`, `perigee_change`, `semi_major_axis_change`, `range` (km or m)
  ■ `inclination_change`, `longitude` (deg)
  ■ `eccentricity_change` (none)
  ■ `delta_v` (m/s, km/s or cm/s)
  ■ `drift_rate` (deg/day)
  ■ `brightness_change` (mag)
● The post ids are in the converted thread file.

A second mission lead then checks one key against its thread.

## 10. Run the trial and read the result

### 10.1 Run it

Replace the 2 numbers in angle brackets with the owner's inputs from section 3.

```
cd ~/handover-trial
docker run --rm --network none --memory 4g --memory-swap 4g --cpus 2 \
  -v "$PWD/trial-data:/data:ro" -v "$PWD/trial-out:/out" holly-handover-trial \
  run --threads /data/threads --keys /data/keys --providers /data/providers.json \
      --model /data/models/<first>.gguf --model /data/models/<second>.gguf \
      --model /data/models/<third>.gguf \
      --holly-peak-gib <Holly's peak in GB> --shift-threads <typical threads> --out /out/run1
```

Allow up to an hour or so for all models together. The models run one after another, each in its own process.

### 10.2 Read the report

Open `trial-out/run1/report.md`. The table has one row per model:

| Column | What it means | What good looks like |
|---|---|---|
| Go | Did it clear every pass mark? | GO |
| Found | The lead's figures it found, and the percentage | 80% or more |
| Precision | Of the figures it kept, how many were right | High; anything below 100% is explained by the next 2 columns |
| Wrong provider | Figures it credited to the wrong provider | 0 |
| Unsupported kept | Figures kept that are not in their post | Always 0; anything else is a fault in the checks, so stop and report it |
| Load s | Seconds to load the model | For information |
| Mean s per thread | Average seconds to read one thread | For information |
| Shift s | Load time plus a typical shift's threads | 300 or less |
| Peak GiB | The most memory the model used | For information |
| Spare GiB | 4 GiB, minus Holly's peak, minus the model's peak | 1 or more |

Under the table, each model has its own section. It lists every pass mark as PASS or FAIL, what the checks dropped, and a **Responsiveness** line: how much slower a small fixed task ran while the model worked. That last figure is a guide to how sluggish Holly's pages would feel during the end-of-shift run. It is reported, not marked.

### 10.3 Review the wrong ones

For every wrong claim kept, open `trial-out/run1/run-<model>.json`, find the claim, open its post in the thread file, and write one line on why it went wrong. The mission lead helps with this.

## 11. Packaging the trial for a machine without internet

If the trial machine is not allowed online, build on a connected Bluestaq machine and carry the result over on approved media:

1. On the connected machine, build the image (step 6.2) and save it to a single file:
   ```
   docker save holly-handover-trial -o holly-handover-trial.tar
   ```
2. Copy `holly-handover-trial.tar` and the model files across.
3. On the trial machine, load the image:
   ```
   docker load -i holly-handover-trial.tar
   ```
4. Carry on from step 6.3. The trial machine never needs the source code or the internet.

To hand someone the trial **code** rather than the image, export it from the repository:

```
git archive --format=zip -o handover-trial-code.zip HEAD trial
```

The zip holds only the `trial/` folder, with no history and none of Holly.

## 12. Clean up

When the owner has the result:

1. Write the short results note: models, PASS or FAIL per mark, timings and memory. It holds **no thread text and no figures from real posts**. Send it to the owner to commit.
2. Delete `trial-data/` and `trial-out/` completely.
3. If the machine will not be used again for the trial, remove the image:
   ```
   docker image rm holly-handover-trial
   ```
4. Revoke the Mattermost personal access token if you made one for the trial.

## 13. If something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| `range of CPUs is from 0.01 to 1.00` (or similar) | The machine, or Docker Desktop, has fewer CPUs than the trial asks for | Give Docker Desktop at least 2 CPUs, or use a machine with 2 or more cores. Don't lower `--cpus`, or the timings won't reflect Holly. |
| `no result within ... or the child died (exit -9)` | The model ran out of its 4 GB and was stopped | The model is too big for Holly. That is a valid NO-GO result: record it and carry on with the others. |
| `Permission denied` writing to `/out` | The trial runs as a non-administrator user (id 10001) and cannot write to the output folder | Make `trial-out` writable: `chmod 777 trial-out` on Linux or macOS, or check the folder's sharing in Docker Desktop. |
| The build stops while downloading | The machine cannot reach PyPI, or a download did not match its pinned fingerprint | Check internet access to `pypi.org`. If a fingerprint fails, stop and report it; never edit `requirements-trial.txt` by hand. |
| `answer keys with no thread file` | A key's `thread_id` doesn't match any converted thread | Check the id at the top of the key file against the thread file. |
| `answer key has malformed claims` | A key uses a quantity or unit that isn't on the list, or a value that isn't a number | Fix the key using the list in section 9.2. |
| A Windows path error on `-v` | PowerShell paths differ | Use the full path, for example `-v C:\handover-trial\trial-out:/out`. |

## 14. Words used in this guide

● **Container, image:** a sealed, repeatable package of software. The image is the package; a container is one run of it. Deleting either leaves the computer as it was.
● **Docker:** the tool that builds images and runs containers.
● **GGUF:** the file format the model runtime reads.
● **Q4_K_M:** a compressed version of a model that uses about a quarter of the memory of the original.
● **Language model:** software that reads and writes text. Here it is only allowed to pull figures out of posts.
● **Answer key:** the mission lead's list of what a perfect reader would find.
● **SHA-256, fingerprint, hash:** a long code that changes if even one byte of a file changes. It proves a file is the one you expect.
● **Personal access token:** a password-like key that lets a script act as you in Mattermost. Treat it like a password.
● **GO, NO-GO:** whether a model cleared every pass mark.
