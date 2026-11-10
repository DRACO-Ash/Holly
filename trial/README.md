# Handover local-model trial harness

Phase 0 of the Handover proposal. The protocol, pass marks and data handling are in `docs/roadmap/handover-trial-plan.md`; this file is the operator's commands. Trial only: nothing here is part of Holly or its upload.

## Layout

```
handover_trial/   claims.py (the 3 checks), threads.py (thread files, Mattermost converter),
                  prompt.py, backend.py (model or stand-in), runner.py (child process, timing,
                  memory), score.py (answer key, pass marks, report), __main__.py (command line)
samples/          SYNTHETIC threads, answer keys, provider list and stand-in replies
tests/            unit tests, standard library only
Dockerfile        the trial container, runtime pinned by hash (requirements-trial.txt)
```

## Windows laptop, no container (Route A)

Python 3.12 for your user only, and llama.cpp's Windows CPU build unzipped into a folder. Full
walkthrough: `docs/roadmap/handover-trial-guide.md`.

```
cd C:\handover-trial\handover-trial-kit\trial
py -3.12 -m unittest discover -s tests
py -3.12 -m handover_trial dry-run --out C:\handover-trial\trial-out\dry
py -3.12 -m handover_trial run --server-exe C:\handover-trial\llama\llama-server.exe `
  --threads <dir> --keys <dir> --providers <file> --model <file.gguf> `
  --holly-peak-gib <measured> --shift-threads <typical> --out C:\handover-trial\trial-out\run1
```

The harness starts `llama-server.exe` per model on 127.0.0.1 only, with 2 threads, a 4,096-token
window and below-normal priority, reads its peak memory, then stops it. Nothing caps memory, so
the score compares the measured peak with Holly's 4 GiB.

## Without a model (checks and dry run only)

```
cd trial
python3 -m unittest discover -s tests
python3 -m handover_trial dry-run --out /tmp/trial-dry
```

## In a container (Route B)

```
docker build -t holly-handover-trial trial/
docker run --rm --network none --entrypoint python holly-handover-trial -m unittest discover -s tests
docker run --rm --network none -v "$PWD/trial-out:/out" holly-handover-trial dry-run --out /out/dry
```

Prepare a data folder on the trial machine, outside any git repository:

```
trial-data/
  providers.json        names, aliases, and author display names mapped to providers
  threads/*.json        one file per thread, converted below
  keys/*.json           the mission lead's answer key, one per thread
  models/*.gguf         the candidate models
```

Convert each exported thread (`GET /api/v4/posts/{root_post_id}/thread` from Mattermost):

```
python3 -m handover_trial convert --export raw/<id>.json --channel <channel> \
    --users users.json --out trial-data/threads/<id>.json
```

`users.json` maps Mattermost user ids to display names, matching the names in `providers.json`.

Run every candidate with the network off and Holly's caps:

```
docker run --rm --network none --memory 4g --memory-swap 4g --cpus 2 \
  -v "$PWD/trial-data:/data:ro" -v "$PWD/trial-out:/out" holly-handover-trial \
  run --threads /data/threads --keys /data/keys --providers /data/providers.json \
      --model /data/models/<first>.gguf --model /data/models/<second>.gguf \
      --holly-peak-gib <measured> --shift-threads <typical> --out /out/run1
```

`trial-out/run1/report.md` is the result; `scores.json` and one `run-<model>.json` per model hold the detail. They contain post ids and figures, never thread text, and stay on the trial machine.

## Answer key format

```
{"thread_id": "<root post id>",
 "claims": [{"post_id": "...", "provider": "NorthStar", "quantity": "period_change", "value": "+25", "unit": "s"}]}
```

Write a sign only when the post writes one. Quantities and their units: `period_change` (s, min), `apogee_change`, `perigee_change`, `semi_major_axis_change`, `range` (km, m), `inclination_change`, `longitude` (deg), `eccentricity_change` (none), `delta_v` (m/s, km/s, cm/s), `drift_rate` (deg/day), `brightness_change` (mag).
