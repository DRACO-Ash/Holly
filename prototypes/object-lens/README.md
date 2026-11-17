# Object Lens prototype

A clickable prototype of the Object Lens (`docs/roadmap/object-lens-proposal.html`) for the hallway test (`docs/roadmap/object-lens-hallway-test.md`). It is not part of Holly's upload: `scripts/package-appstore.sh` does not package `prototypes/`, and nothing here is imported by `frontend/`.

## Build

```
cd frontend && npm ci --ignore-scripts && cd ..
sh prototypes/object-lens/build.sh
```

The build copies `frontend/` to a temporary folder, adds `overlay/`, applies `patch.py`, type-checks, builds with `vite.proto.config.ts` and folds the result into one file, `dist/holly-object-lens-prototype.html` (ignored by Git). Copy it to `docs/roadmap/object-lens-prototype.html` to publish a new build. Holly's own source and `frontend/node_modules` are read, never written.

`patch.py` makes exact replacements that must each match once; if a Holly change moves one of those lines, the build stops and names it.

## Layout

● `overlay/src/proto/data.ts`: the synthetic world, with the two matched test objects.
● `overlay/src/proto/mock.ts`: answers every API call in the browser, through an axios adapter.
● `overlay/src/proto/lens/`: the lens (context, links, drawer, Find palette, watch strip).
● `overlay/src/proto/console/`: the facilitator console and the 5 tasks with their answer key.
● `overlay/src/proto/proto.css`: styles, on Holly's tokens.
● `patch.py`, `inline.py`, `build.sh`, `overlay/vite.proto.config.ts`: the build.

## Rules it keeps

● Synthetic data only; no network call (the built file was checked for both).
● No language model and nothing sent outside the page, as the owner decided on 6 November 2026.
● Prototype code: it has no tests of its own and has not been through the engineering or security gates. Phase 1, if approved, is written into `frontend/` under the normal loop and gates.
