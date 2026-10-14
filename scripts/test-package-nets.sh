#!/bin/sh
# test-package-nets.sh :: proves check-package.sh refuses what it claims to and accepts a clean
# upload. Each case is a synthetic upload zip carrying one planted problem, including the names
# that once slipped past the content net (brackets, a newline, a tab). Run by verify.sh.
# Needs python3, unzip and node.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/holly-net-test.XXXXXX")"
trap 'rm -rf -- "$WORK"' EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# AWS's documented example access key, split so this file's own source never matches the rule.
KEY="AKIA""IOSFODNN7EXAMPLE"
NL='
'
TAB="$(printf '\t')"
n=0

zip_of() {  # $1: output zip, then member name and content pairs. Content utf16:TEXT is UTF-16LE.
  python3 - "$@" <<'PY'
import sys
import zipfile

out, *pairs = sys.argv[1:]
with zipfile.ZipFile(out, "w") as archive:
    for name, content in zip(pairs[0::2], pairs[1::2]):
        kind, sep, text = content.partition(":")
        data = text.encode("utf-16-le") if sep and kind == "utf16" else content.encode()
        archive.writestr(name, data)
PY
}

check() {  # $1: pass or refuse, $2: text the output must hold, $3: label, then planted members
  expected="$1"
  fragment="$2"
  label="$3"
  shift 3
  n=$((n + 1))
  zip_of "$WORK/case$n.zip" Dockerfile 'FROM scratch' requirements.txt '' pyproject.toml '' "$@"
  if out="$(sh "$HERE/check-package.sh" "$WORK/case$n.zip" 2>&1)"; then got=pass; else got=refuse; fi
  if [ "$got" != "$expected" ]; then
    printf 'FAIL: %s: expected %s, got %s\n%s\n' "$label" "$expected" "$got" "$out"; exit 1
  fi
  case "$out" in
    *"$fragment"*) ;;
    *) printf 'FAIL: %s: the output lacks "%s"\n%s\n' "$label" "$fragment" "$out"; exit 1 ;;
  esac
  echo "ok: $label ($got)"
}

check pass "files scanned, clean" "a clean upload"
check refuse "secret-scan rules matched" "a key in an ordinary file" \
  src/app/leak.py "K = \"$KEY\""
check refuse "secret-scan rules matched" "a key behind a bracketed name" \
  "src/app/[leak].py" "K = \"$KEY\""
check refuse "secret-scan rules matched" "a bracketed name beside a clean namesake" \
  src/app/x.py 'X = 1' "src/app/[x].py" "K = \"$KEY\""
check refuse "control character" "a newline in a name" \
  "src/app/leak${NL}b.py" "K = \"$KEY\""
check refuse "control character" "a tab in a name" \
  "src/app/leak${TAB}b.py" "K = \"$KEY\""
check refuse "secret-scan rules matched" "a key in UTF-16LE text" \
  tests/fixture.txt "utf16:K = \"$KEY\""
check refuse "banned path" "an archive inside the upload" tests/data.zip 'PK'
check refuse "banned path" "an environment file by name" src/app/prod.env 'X=1'

# A scan that cannot run must refuse as "could not scan", never pass and never pose as a match.
scan_fails() {  # $1: label, $2: expected file count, $3: hook path
  n=$((n + 1))
  if out="$(node "$HERE/scan-package.mjs" "$WORK/clean" "$2" "$3" 2>&1)"; then
    printf 'FAIL: %s: the scan passed\n' "$1"; exit 1
  fi
  case "$out" in
    *"could not scan"*) echo "ok: $1 (refuse)" ;;
    *) printf 'FAIL: %s: the output lacks "could not scan"\n%s\n' "$1" "$out"; exit 1 ;;
  esac
}
mkdir "$WORK/clean"
printf 'X = 1\n' > "$WORK/clean/a.py"
scan_fails "a missing secret-scan hook" 1 "$WORK/no-such-hook.mjs"
scan_fails "fewer files than the archive lists" 2 "$HERE/../.claude/hooks/secret-scan.mjs"

echo "upload nets: all $n cases behaved"
