# Handover trial: a step-by-step guide for first-timers

Bluestaq Limited · Holly · 10 November 2026

This guide walks you through running the Handover local-model trial from start to finish, assuming you have never done anything like it before. The trial plan (`docs/roadmap/handover-trial-plan.md`) says **why** and **what passes**; this guide says **how**.

## 1. What the trial is, in one minute

Holly's planned Handover tab will use a small language model, running inside Holly, to read Mattermost threads near the end of each shift and pull out what each provider said (for example "NorthStar: +25 s period change"). Before building that into Holly, we test whether a small model can do the job well enough on Holly's fixed allocation of **4 GB of memory and 2 CPUs**.

The trial runs a few candidate models over 5 real threads and compares what each one finds with what a mission lead found by hand. It then gives each model a plain **GO** or **NO-GO**.

**What the trial is not:**
● It is not deployed anywhere: not to the App Store, not to a server. It is a set of commands you run on one computer for about a day, then delete.
● It does not touch the live Holly app, its database or its settings.
● It does not send anything outside Bluestaq: the model listens only to your own computer.

## 2. What it changes in Holly: nothing

| Area | Effect | Why |
|---|---|---|
| The Holly app on the App Store | None | The trial runs on your computer and never connects to Holly. |
| Holly's upload package | None | The packaging script lists exactly which files go into an upload (`PATHS` in `scripts/package-appstore.sh`), and `trial/` is not on it. |
| The App Store pipeline and code quality scan | None | They only see the upload package. |
| Holly's tests and checks | None | They cover `src/`, `tests/` and `frontend/` only. |
| Holly's version number | None | Only changes to the upload bump the version. |
| Holly's database, settings and users | None | The trial reads exported copies of threads, never Holly. |
| The repository | Adds `trial/` and 3 documents | Real data is never committed. It lives outside the code folder, and `trial/.gitignore` blocks it anyway. |

## 3. Pick your route

There are 2 ways to run the trial. They use the same code, the same checks and the same scoring.

| | Route A: Windows laptop, no container | Route B: a container |
|---|---|---|
| For | A Windows laptop where you cannot install Docker or make a virtual machine | A Linux machine, or any machine where Docker or Podman is allowed |
| You install | Python, for your user only (no admin rights), and llama.cpp's ready-built Windows programs, unzipped into a folder (no install) | Docker or Podman |
| Memory limit | Not enforced. The trial measures the model's peak memory and the score compares it with Holly's 4 GB. | Enforced at 4 GB by the container |
| Network | The model listens on your own computer only (127.0.0.1) | Switched off inside the container |

Sections 5 to 13 give Route A first, then Route B.

## 4. Before you start: the checklist

| # | Item | From whom |
|---|---|---|
| 1 | The pass marks confirmed (see the trial plan) | Owner |
| 2 | Holly's own peak memory, read from the App Store metrics for the `holly` app | Owner or platform team |
| 3 | How many threads a typical shift's run would read | Owner, with a mission lead |
| 4 | Approval to copy 5 real Mattermost threads onto the trial computer | Data owner |
| 5 | The trial computer approved for that data (the deciding point: see section 5) | ISM |
| 6 | A mission lead booked for 2 to 3 hours to write the answer keys | Owner |
| 7 | The model files (section 9) | You |

## 5. What you need

### Route A: your Windows laptop

● **Windows 10 or 11, 64-bit**, with 8 GB of memory or more and 2 or more CPU cores.
● **About 10 GB free disk** for Python, llama.cpp, the models (up to about 5 GB) and the outputs.
● **Approval for the data.** The laptop will hold 5 real threads for a day or so. It must be approved for whatever marking they carry.
● **Permission to run 2 unsigned programs** you unzip (`llama-server.exe` and its libraries). Windows security, such as SmartScreen, Defender or an application allow-list, may block them. If so, IT needs to allow that one folder, or you need a different machine.
● **Internet, during setup only:** python.org, llama.cpp's GitHub releases page and the model host. The trial run itself needs no network.
● **curl.exe**, which is built into Windows 10 and 11, for the Mattermost export.

### Route B: a container machine

● Linux, or Windows or macOS with Docker Desktop or Podman Desktop. Docker Desktop's free terms cover only small organisations, so check the licence with IT. Podman Desktop is free.
● 2 or more CPU cores, 8 GB of memory and 15 GB of free disk.
● With Docker Desktop, give it at least 6 GB of memory and 2 CPUs under Settings, Resources.
● Internet access to PyPI while building only.

### Both routes

● The trial kit: `handover-trial-kit.zip`, or the `trial/` folder from the Holly repository.
● A way to export Mattermost threads: your own personal access token, or a Mattermost administrator. Whether personal tokens are switched on for Bluestaq's Mattermost is `TBC, re-verify`.

## 6. Where to put everything

Make one working folder, **outside** any code repository. On Route A that is `C:\handover-trial`:

```
C:\handover-trial\
  handover-trial-kit\    the kit, unzipped; never put data in here
    trial\               the trial code (you run commands from here)
    docs\                this guide, the plan and the interactive brief
  llama\                 llama.cpp's Windows programs, unzipped (Route A only)
  trial-data\            everything real
    providers.json       the provider list
    users.json           Mattermost user ids to usernames (step 10.3)
    raw\                 the threads as exported from Mattermost
    threads\             the threads converted for the trial
    keys\                the mission lead's answer keys
    models\              the model files
  trial-out\             the results
```

On Route B, use the same layout under `~/handover-trial`, with no `llama` folder.

## 7. Set up

### Route A: Windows laptop

**7.1 Unzip the kit.** Unzip `handover-trial-kit.zip` into `C:\handover-trial`, so `C:\handover-trial\handover-trial-kit\trial` exists.

**7.2 Install Python 3.12 for your user only.**
1. From python.org, download the **Windows installer (64-bit)** for the latest Python 3.12 release.
2. Run it.
3. On the first screen, **untick "Use admin privileges when installing py.exe"** and **tick "Add python.exe to PATH"**.
4. Choose **Install Now**. It installs into your own profile, with no admin rights needed.

Check it worked: open **PowerShell** (Start, type PowerShell) and run:

```
py -3.12 --version
```

You should see `Python 3.12.` and a number.

**7.3 Get llama.cpp's Windows programs.**
1. On the llama.cpp project's GitHub **Releases** page (`github.com/ggml-org/llama.cpp/releases`), choose a release **at least 15 days old**.
2. Download its **Windows CPU build for x64**: the zip whose name includes `win`, `cpu` and `x64`.
3. Write down the release tag (it looks like `b` followed by digits) and the file's fingerprint: `Get-FileHash <the zip>`.
4. Unzip it into `C:\handover-trial\llama`. Check that `C:\handover-trial\llama\llama-server.exe` exists. llama.cpp uses the MIT licence.

**7.4 Run the self-tests.** These check the trial's own code; they use no model and no real data.

```
cd C:\handover-trial\handover-trial-kit\trial
py -3.12 -m unittest discover -s tests
```

You should see `OK` on the last line.

**7.5 Run the dry run.** This runs the whole trial on made-up threads, with a stand-in instead of a model.

```
py -3.12 -m handover_trial dry-run --out C:\handover-trial\trial-out\dry
```

The report ends in **NO-GO**. That is correct: the stand-in was built to make mistakes, and the report shows each one being caught. The table row reads `7/10 (70%)`, with `1` under Wrong provider and `0` under Unsupported kept.

### Route B: container

```
cd ~/handover-trial/handover-trial-kit
docker build -t holly-handover-trial trial/
docker run --rm --network none --entrypoint python holly-handover-trial -m unittest discover -s tests
mkdir -p ~/handover-trial/trial-out && chmod 777 ~/handover-trial/trial-out
docker run --rm --network none --memory 4g --memory-swap 4g --cpus 2 \
  -v ~/handover-trial/trial-out:/out holly-handover-trial dry-run --out /out/dry
```

The build compiles the model runtime from source, so it takes several minutes. Every download is checked against a fingerprint pinned in `trial/requirements-trial.txt`. The tests end in `OK`, and the dry run ends in NO-GO as described above. With Podman, type `podman` where these commands say `docker`.

## 8. A word on the network (Route A)

`llama-server.exe` is a small local web service. The trial starts it, binds it to `127.0.0.1` so that only your own computer can reach it, and stops it when each model finishes. It only loads the model file you give it and does not download anything.

If Windows shows a firewall prompt when it starts, choose **Cancel** or **Don't allow**: the trial only uses your computer's own internal address, which the firewall doesn't block. For extra assurance you can disconnect from the network (Wi-Fi and VPN) while step 12 runs. It needs none.

## 9. Get the models

1. Download the 4-bit `Q4_K_M` GGUF file of each candidate in the trial plan's table from a source your team trusts:
   ■ Qwen2.5-1.5B-Instruct;
   ■ SmolLM2-1.7B-Instruct;
   ■ Qwen2.5-0.5B-Instruct;
   ■ Phi-3.5-mini-instruct, as the stretch test.
2. **Check the licence** on each model's page. It must be MIT or Apache-2.0. Write it down.
3. **Record each file's fingerprint (SHA-256):**
   ■ Windows: `Get-FileHash C:\handover-trial\trial-data\models\*.gguf`
   ■ Linux: `sha256sum *.gguf`
4. Put the files in `trial-data\models`.

The report also prints each model's fingerprint, so you can confirm the file you ran is the file you recorded.

## 10. Get the threads

### 10.1 Choose 5

With a mission lead, pick one thread of each kind:
● a manoeuvre where providers disagreed;
● an RPO;
● a photometric change;
● a separation or other event type;
● the longest, noisiest thread of the last month.

### 10.2 Find each thread's id

In Mattermost, open the first post of the thread and choose **Copy Link**. The id is the last part of the link, after `/pl/`.

### 10.3 Export it

Put your token in a variable so it never lands in a file or your history. In each command, replace `<mattermost-host>` with your Mattermost address and `<id>` with the thread id.

Route A (PowerShell):
```
$MM_TOKEN = Read-Host -MaskInput "Mattermost token"
curl.exe -sS -H "Authorization: Bearer $MM_TOKEN" `
  https://<mattermost-host>/api/v4/posts/<id>/thread `
  -o C:\handover-trial\trial-data\raw\<id>.json
```

`-MaskInput` needs PowerShell 7. In the older Windows PowerShell 5.1, use `$MM_TOKEN = Read-Host "Mattermost token"` instead; the token is then visible on screen as you paste, so make sure nobody is watching. Always type `curl.exe`, not `curl`, which PowerShell treats as a different command.

Then fetch the usernames of everyone who posted, so the trial can tell which analyst speaks for which provider. Each post in an export has a `user_id`; list them:

```
'["<user id 1>","<user id 2>"]' | Out-File -Encoding ascii C:\handover-trial\trial-data\ids.json
curl.exe -sS -X POST -H "Authorization: Bearer $MM_TOKEN" -H "Content-Type: application/json" `
  --data-binary "@C:\handover-trial\trial-data\ids.json" `
  https://<mattermost-host>/api/v4/users/ids -o C:\handover-trial\trial-data\users.json
```

Route B (Linux):
```
read -s MM_TOKEN
curl -sS -H "Authorization: Bearer $MM_TOKEN" \
  https://<mattermost-host>/api/v4/posts/<id>/thread -o ~/handover-trial/trial-data/raw/<id>.json
curl -sS -X POST -H "Authorization: Bearer $MM_TOKEN" -H "Content-Type: application/json" \
  -d '["<user id 1>","<user id 2>"]' \
  https://<mattermost-host>/api/v4/users/ids -o ~/handover-trial/trial-data/users.json
```

Close the window when you are done so the token is forgotten. If personal tokens are switched off, a Mattermost administrator can export the threads for you.

### 10.4 Convert it

Route A:
```
cd C:\handover-trial\handover-trial-kit\trial
py -3.12 -m handover_trial convert --export C:\handover-trial\trial-data\raw\<id>.json `
  --channel <channel name> --users C:\handover-trial\trial-data\users.json `
  --out C:\handover-trial\trial-data\threads\<id>.json
```

Route B:
```
cd ~/handover-trial
docker run --rm --network none -v "$PWD/trial-data:/data" holly-handover-trial \
  convert --export /data/raw/<id>.json --channel <channel name> --users /data/users.json \
  --out /data/threads/<id>.json
```

## 11. Write the provider list and the answer keys

### 11.1 The provider list

Create `trial-data\providers.json` in Notepad. List each provider with any other names it goes by, and map each Mattermost username that posts on a provider's behalf to that provider:

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

Only the owner decides which providers go on the list.

### 11.2 The answer keys

The mission lead writes one file per thread in `trial-data\keys`, **before seeing any model output**, listing every figure a provider gave in that thread:

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
● The post ids are in the converted thread files; open them in Notepad.

A second mission lead then checks one key against its thread.

## 12. Run the trial and read the result

### 12.1 Run it

Replace the 2 numbers in angle brackets with the owner's inputs from section 4. The models run one after another; allow up to an hour or so. Close other heavy programs first so the timings are fair.

Route A:
```
cd C:\handover-trial\handover-trial-kit\trial
py -3.12 -m handover_trial run `
  --server-exe C:\handover-trial\llama\llama-server.exe `
  --threads C:\handover-trial\trial-data\threads --keys C:\handover-trial\trial-data\keys `
  --providers C:\handover-trial\trial-data\providers.json `
  --model C:\handover-trial\trial-data\models\<first>.gguf `
  --model C:\handover-trial\trial-data\models\<second>.gguf `
  --model C:\handover-trial\trial-data\models\<third>.gguf `
  --holly-peak-gib <Holly's peak in GB> --shift-threads <typical threads> `
  --out C:\handover-trial\trial-out\run1
```

The trial starts `llama-server.exe` for each model with Holly's settings: 2 CPU threads, a 4,096-token window and below-normal priority. It reads every thread, records the server's peak memory, then stops it.

Route B:
```
cd ~/handover-trial
docker run --rm --network none --memory 4g --memory-swap 4g --cpus 2 \
  -v "$PWD/trial-data:/data:ro" -v "$PWD/trial-out:/out" holly-handover-trial \
  run --threads /data/threads --keys /data/keys --providers /data/providers.json \
      --model /data/models/<first>.gguf --model /data/models/<second>.gguf \
      --model /data/models/<third>.gguf \
      --holly-peak-gib <Holly's peak in GB> --shift-threads <typical threads> --out /out/run1
```

### 12.2 Read the report

Open `trial-out\run1\report.md` in Notepad, or in any Markdown viewer. The table has one row per model:

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

Under the table, each model has its own section listing every pass mark as PASS or FAIL, what the checks dropped, and a **Responsiveness** line: how much slower a small fixed task ran while the model worked. That line is reported, not marked. On a laptop it also reflects whatever else the laptop was doing at the time.

**Route A note:** the laptop does not stop a model that goes over 4 GB. The **Spare GiB** column and the memory pass mark catch it instead, so a model too big for Holly still shows as NO-GO.

### 12.3 Review the wrong ones

For every wrong claim a model kept, open `trial-out\run1\run-<model>.json`, find the claim, open its post in the thread file, and write one line on why it went wrong. The mission lead helps with this.

## 13. Moving the trial to a computer without internet

Route A: do steps 7.2 and 7.3 and section 9 on a connected Bluestaq computer. Then copy across, on approved media:
● the Python installer;
● the `llama` folder;
● the model files;
● the kit zip.

Install and unzip them on the trial computer the same way.

Route B: build on a connected machine, `docker save holly-handover-trial -o holly-handover-trial.tar`, copy the file and the models across, then `docker load -i holly-handover-trial.tar` on the trial machine.

To hand someone just the trial **code**, from the Holly repository: `git archive --format=zip -o handover-trial-code.zip HEAD trial`.

## 14. Clean up

When the owner has the result:

1. Write the short results note: models, PASS or FAIL per mark, timings and memory. It holds **no thread text and no figures from real posts**. Send it to the owner to commit.
2. Delete the real data and results:
   ■ Route A: `Remove-Item -Recurse -Force C:\handover-trial\trial-data, C:\handover-trial\trial-out`
   ■ Route B: `rm -rf ~/handover-trial/trial-data ~/handover-trial/trial-out`
3. Remove the tools if you are finished:
   ■ Route A: delete `C:\handover-trial` and uninstall Python from Settings, Apps if you no longer need it.
   ■ Route B: `docker image rm holly-handover-trial`.
4. Revoke the Mattermost personal access token if you made one for the trial.

## 15. If something goes wrong

| What you see | What it means | What to do |
|---|---|---|
| `py` is not recognised | Python is not installed, or not on the PATH | Re-run the Python installer and tick "Add python.exe to PATH". Then open a new PowerShell window. |
| Windows blocks `llama-server.exe`, or it vanishes after unzipping | Windows security does not allow unsigned programs | Ask IT to allow `C:\handover-trial\llama`, or use another computer. Don't work around it. |
| A message about a missing `.dll` file, for example `VCRUNTIME140.dll` | The Microsoft Visual C++ runtime is missing | Ask IT to install the Microsoft Visual C++ Redistributable, which needs admin rights. |
| `llama-server stopped while loading` | The server could not start: a wrong model path, a damaged model file, or not enough memory | Check the path and the file's fingerprint. If memory ran out, the model is too big: a valid NO-GO. |
| `llama-server was not ready within ...` | The model took too long to load | Close other programs and try again; if it persists, record it as a NO-GO for that model. |
| `no result within ... or the child died (exit -9)` (Route B) | The model ran out of its 4 GB and was stopped | That model is too big for Holly: a valid NO-GO. Record it and carry on. |
| `range of CPUs is from 0.01 to 1.00`, or similar (Route B) | The machine, or Docker Desktop, has fewer CPUs than the trial asks for | Give Docker Desktop at least 2 CPUs, or use a machine with 2 or more cores. |
| `Permission denied` writing results (Route B) | The container runs as an ordinary user | Make `trial-out` writable: `chmod 777 trial-out`. |
| `answer keys with no thread file` | A key's `thread_id` doesn't match any converted thread | Check the id at the top of the key against the thread file. |
| `answer key has malformed claims` | A key uses a quantity or unit that isn't on the list, or a value that isn't a number | Fix the key using the list in section 11.2. |
| A firewall prompt when the trial starts (Route A) | Windows noticed `llama-server.exe` listening | Choose Cancel or Don't allow; the trial still works (section 8). |

## 16. Words used in this guide

● **llama.cpp, llama-server:** free software (MIT licence) that runs language models on an ordinary processor. `llama-server.exe` is its program that answers requests from the trial.
● **Container, image, Docker, Podman (Route B):** tools that run software in a sealed, repeatable package.
● **GGUF:** the file format the model runtime reads.
● **Q4_K_M:** a compressed version of a model that uses about a quarter of the memory of the original.
● **Language model:** software that reads and writes text. Here it is only allowed to pull figures out of posts.
● **Answer key:** the mission lead's list of what a perfect reader would find.
● **SHA-256, fingerprint, hash:** a long code that changes if even one byte of a file changes. It proves a file is the one you expect.
● **127.0.0.1:** your own computer's internal address. A service listening only there cannot be reached from any other machine.
● **Personal access token:** a password-like key that lets a script act as you in Mattermost. Treat it like a password.
● **GO, NO-GO:** whether a model cleared every pass mark.
