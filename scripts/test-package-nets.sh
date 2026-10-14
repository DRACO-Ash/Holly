#!/bin/sh
# test-package-nets.sh :: proves check-package.sh refuses what it claims to and accepts a clean
# upload. Each case is a synthetic upload zip carrying one planted problem, including every
# shape that once slipped past the nets: bracketed and control-character names, archives under
# an upper-case or unlisted name, compressed streams, and UTF-16 off its usual alignment or byte
# order. A hook that crashes must refuse too. Run by verify.sh. Needs python3, unzip and node.
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

# $1: output zip, then member name and content pairs. A content of KIND:TEXT encodes TEXT as
# utf16 (UTF-16LE), utf16be, oddutf16 (UTF-16LE after one leading byte), zip (a zip holding it)
# or gzip (a gzip stream of it), or makes the member a symlink to TEXT (symlink); any other
# content is stored as UTF-8.
zip_of() {
  python3 - "$@" <<'PY'
import gzip
import io
import stat
import sys
import zipfile


def encode(content):
    kind, sep, text = content.partition(":")
    if not sep:
        return content.encode()
    if kind == "utf16":
        return text.encode("utf-16-le")
    if kind == "utf16be":
        return text.encode("utf-16-be")
    if kind == "oddutf16":
        return b"\x01" + text.encode("utf-16-le")
    if kind == "gzip":
        return gzip.compress(text.encode())
    if kind == "zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as inner:
            inner.writestr("xl/connections.xml", text)
        return buffer.getvalue()
    return content.encode()


out, *pairs = sys.argv[1:]
with zipfile.ZipFile(out, "w") as archive:
    for name, content in zip(pairs[0::2], pairs[1::2]):
        if content.startswith("symlink:"):
            link = zipfile.ZipInfo(name)
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, content.removeprefix("symlink:"))
        else:
            archive.writestr(name, encode(content))
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
check refuse "secret-scan rules matched" "a key in UTF-16LE text after one leading byte" \
  tests/fixture.txt "oddutf16:K = \"$KEY\""
check refuse "secret-scan rules matched" "a key in UTF-16BE text" \
  tests/fixture.txt "utf16be:K = \"$KEY\""
check refuse "banned path" "an archive inside the upload" tests/data.zip 'PK'
check refuse "banned path" "an archive with an upper-case extension" tests/DATA.ZIP 'PK'
check refuse "banned path" "a zip container named as a spreadsheet" \
  tests/fixtures/ops-report.xlsx "zip:K = \"$KEY\""
check refuse "could not scan" "a zip container under an unlisted extension" \
  tests/fixtures/ops-report.dat "zip:K = \"$KEY\""
check refuse "could not scan" "a gzip stream under a neutral name" \
  tests/fixtures/data.bin "gzip:K = \"$KEY\""
check refuse "banned path" "an environment file by name" src/app/prod.env 'X=1'
check refuse "could not scan" "a symlink member" tests/fixtures/link.txt 'symlink:/etc/hostname'

# The required-member check: an upload without its pytest configuration is refused.
n=$((n + 1))
zip_of "$WORK/case$n.zip" Dockerfile 'FROM scratch' requirements.txt ''
if out="$(sh "$HERE/check-package.sh" "$WORK/case$n.zip" 2>&1)"; then
  echo "FAIL: a missing pyproject.toml: the package passed"; exit 1
fi
case "$out" in
  *"missing pyproject.toml"*) echo "ok: a missing pyproject.toml (refuse)" ;;
  *) printf 'FAIL: a missing pyproject.toml: the output lacks the reason\n%s\n' "$out"; exit 1 ;;
esac

# A scan that cannot run, or a hook that starts and then fails, must refuse as "could not
# scan", never pass and never pose as a match.
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
printf 'process.exit(1);\n' > "$WORK/hook-exits-1.mjs"
printf "process.kill(process.pid, 'SIGKILL');\n" > "$WORK/hook-killed.mjs"
printf "process.stdout.write('x'.repeat(2 * 1024 * 1024));\n" > "$WORK/hook-floods.mjs"
scan_fails "a missing secret-scan hook" 1 "$WORK/no-such-hook.mjs"
scan_fails "a hook that exits 1" 1 "$WORK/hook-exits-1.mjs"
scan_fails "a hook stopped by a signal" 1 "$WORK/hook-killed.mjs"
scan_fails "a hook whose output overflows the buffer (a spawn error)" 1 "$WORK/hook-floods.mjs"
scan_fails "fewer files than the archive lists" 2 "$HERE/../.claude/hooks/secret-scan.mjs"

echo "upload nets: all $n cases behaved"
