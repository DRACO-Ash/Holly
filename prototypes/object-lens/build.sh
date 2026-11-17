#!/bin/sh
# Build the Object Lens prototype: a scratch copy of Holly's frontend, the prototype overlaid and
# patched in, type-checked, built and folded into one offline HTML file in dist/.
# Needs frontend/node_modules installed (cd frontend && npm ci --ignore-scripts), python3 and node.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT INT TERM
[ -d "$ROOT/frontend/node_modules" ] || { echo "build.sh: install frontend/node_modules first"; exit 1; }
(cd "$ROOT/frontend" && tar --exclude=./node_modules --exclude=./dist --exclude=./coverage -cf - .) | (cd "$WORK" && tar -xf -)
# Read-only use: the build reads packages from Holly's install and writes only inside $WORK.
ln -s "$ROOT/frontend/node_modules" "$WORK/node_modules"
cp -R "$HERE/overlay/." "$WORK/"
python3 "$HERE/patch.py" "$WORK"
(cd "$WORK" && npx tsc --noEmit -p . && npx vite build --config vite.proto.config.ts --logLevel warn)
python3 "$HERE/inline.py" "$WORK/dist-proto" "$HERE/dist/holly-object-lens-prototype.html"
