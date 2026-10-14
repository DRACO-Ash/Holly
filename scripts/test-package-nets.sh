#!/bin/sh
# test-package-nets.sh :: proves the upload nets refuse what they claim to and accept a clean
# upload. Synthetic upload zips each carry one planted problem, covering every shape that once
# slipped past the nets: bracketed and control-character names; archives under an upper-case or
# unlisted name; compressed streams with or without a signature (zlib, raw deflate, LZMA-alone,
# brotli, a zipapp); and UTF-16 without a byte-order mark. Direct runs of the scanner prove that
# a hook which crashes, floods or hangs refuses, and that the binary allowlist names what it
# lets through. A last case packages HEAD for real. Run by verify.sh; needs python3, unzip and
# node.
set -eu

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
HOOK="$ROOT/.claude/hooks/secret-scan.mjs"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/holly-net-test.XXXXXX")"
trap 'rm -rf -- "$WORK"' EXIT
# dash runs the EXIT trap on a normal exit or a set -e failure, not on a signal: exit first.
trap 'exit 130' INT
trap 'exit 143' TERM

# AWS's documented example access key, split so this file's own source never matches the rule.
KEY="AKIA""IOSFODNN7EXAMPLE"
LINE="K = \"$KEY\""
NL='
'
TAB="$(printf '\t')"
n=0

# $1: output zip, then member name and content pairs. A content of KIND:TEXT encodes TEXT as
# named below; any other content is stored as UTF-8.
zip_of() {
  python3 - "$@" <<'PY'
import bz2
import codecs
import gzip
import io
import lzma
import random
import stat
import sys
import tarfile
import zipfile
import zlib


def inner_zip(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as inner:
        inner.writestr("xl/connections.xml", text)
    return buffer.getvalue()


def tar_of(text):
    buffer = io.BytesIO()
    data = text.encode()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        info = tarfile.TarInfo("inner.txt")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def raw_deflate(text):
    compressor = zlib.compressobj(wbits=-15)
    return compressor.compress(text.encode()) + compressor.flush()


ENCODERS = {
    "utf16": lambda t: t.encode("utf-16-le"),
    "utf16bom": lambda t: codecs.BOM_UTF16_LE + t.encode("utf-16-le"),
    "utf16bebom": lambda t: codecs.BOM_UTF16_BE + t.encode("utf-16-be"),
    "oddutf16": lambda t: b"\x01" + t.encode("utf-16-le"),
    "gzip": lambda t: gzip.compress(t.encode()),
    "zlib": lambda t: zlib.compress(t.encode()),
    "deflate": raw_deflate,
    "lzmaalone": lambda t: lzma.compress(t.encode(), format=lzma.FORMAT_ALONE),
    "bzip2": lambda t: bz2.compress(t.encode()),
    "xz": lambda t: lzma.compress(t.encode(), format=lzma.FORMAT_XZ),
    "tar": tar_of,
    "zip": inner_zip,
    "zipapp": lambda t: b"#!/usr/bin/env python3\n" + inner_zip(t),
    "random": lambda t: random.Random(t).randbytes(256),
    "magic": lambda t: bytes.fromhex(t) + bytes(64),
    "file": lambda t: open(t, "rb").read(),
}

out, *pairs = sys.argv[1:]
with zipfile.ZipFile(out, "w") as archive:
    for name, content in zip(pairs[0::2], pairs[1::2]):
        kind, sep, text = content.partition(":")
        if sep and kind == "symlink":
            link = zipfile.ZipInfo(name)
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, text)
        elif sep and kind in ENCODERS:
            archive.writestr(name, ENCODERS[kind](text))
        else:
            archive.writestr(name, content.encode())
PY
}

expect() {  # $1: pass or refuse, $2: text the output must hold, $3: label, $4: exit status, $5: output
  n=$((n + 1))
  if [ "$4" = 0 ]; then got=pass; else got=refuse; fi
  if [ "$got" != "$1" ]; then
    printf 'FAIL: %s: expected %s, got %s\n%s\n' "$3" "$1" "$got" "$5"; exit 1
  fi
  case "$5" in
    *"$2"*) echo "ok: $3 ($got)" ;;
    *) printf 'FAIL: %s: the output lacks "%s"\n%s\n' "$3" "$2" "$5"; exit 1 ;;
  esac
}

# An upload with the required members plus the planted members given.
check() {  # $1: pass or refuse, $2: text the output must hold, $3: label, then planted members
  expected="$1"
  fragment="$2"
  label="$3"
  shift 3
  zip_of "$WORK/case$n.zip" Dockerfile 'FROM scratch' requirements.txt '' pyproject.toml '' "$@"
  status=0
  out="$(sh "$HERE/check-package.sh" "$WORK/case$n.zip" 2>&1)" || status=$?
  expect "$expected" "$fragment" "$label" "$status" "$out"
}

# The scanner run directly on a prepared directory, with a chosen hook and allowlist.
scan() {  # $1: pass or refuse, $2: text, $3: label, $4: dir, $5: expected count, $6: hook, $7: allowlist
  status=0
  out="$(node "$HERE/scan-package.mjs" "$4" "$5" "$6" "$7" 2>&1)" || status=$?
  expect "$1" "$2" "$3" "$status" "$out"
}

# Names and plain text.
check pass "text files scanned, clean" "a clean upload"
check pass "text files scanned, clean" "a text file that begins like a bzip2 signature" \
  docs.txt 'BZh is how a bzip2 stream starts'
check refuse "secret-scan rules matched" "a key in an ordinary file" src/app/leak.py "$LINE"
check refuse "secret-scan rules matched" "a key behind a bracketed name" "src/app/[leak].py" "$LINE"
check refuse "secret-scan rules matched" "a bracketed name beside a clean namesake" \
  src/app/x.py 'X = 1' "src/app/[x].py" "$LINE"
check refuse "control character" "a newline in a name" "src/app/leak${NL}b.py" "$LINE"
check refuse "control character" "a tab in a name" "src/app/leak${TAB}b.py" "$LINE"
check refuse "banned path" "an environment file by name" src/app/prod.env 'X=1'
check refuse "banned path" "an archive inside the upload" tests/data.zip 'PK'
check refuse "banned path" "an archive with an upper-case extension" tests/DATA.ZIP 'PK'
check refuse "banned path" "a zip container named as a spreadsheet" tests/report.xlsx "zip:$LINE"
check refuse "could not scan" "a symlink member" tests/link.txt 'symlink:/etc/hostname'

# UTF-16 is text only with a byte-order mark; without one it cannot be read safely.
check refuse "secret-scan rules matched" "a key in UTF-16LE text with a byte-order mark" \
  tests/fixture.txt "utf16bom:$LINE"
check refuse "secret-scan rules matched" "a key in UTF-16BE text with a byte-order mark" \
  tests/fixture.txt "utf16bebom:$LINE"
check refuse "is not text" "UTF-16LE text without a byte-order mark" tests/fixture.txt "utf16:$LINE"
check refuse "is not text" "UTF-16 text after one leading byte" tests/fixture.txt "oddutf16:$LINE"

# Anything that is not text is refused under a neutral name, with or without a signature.
check refuse "holds zip content" "a zip container under an unlisted extension" \
  tests/report.dat "zip:$LINE"
check refuse "holds gzip content" "a gzip stream" tests/data.bin "gzip:$LINE"
check refuse "is not text" "a zlib stream" tests/data.bin "zlib:$LINE"
check refuse "is not text" "a raw deflate stream, which has no signature" tests/data.bin "deflate:$LINE"
check refuse "is not text" "an LZMA-alone stream" tests/data.bin "lzmaalone:$LINE"
node -e 'require("fs").writeFileSync(process.argv[1], require("zlib").brotliCompressSync(Buffer.from(process.argv[2])))' \
  "$WORK/brotli.bin" "$LINE"
check refuse "is not text" "a brotli stream" tests/data.bin "file:$WORK/brotli.bin"
check refuse "is not text" "a zipapp, a zip behind a shebang" tests/tool.pyz "zipapp:$LINE"
check refuse "is not text" "random bytes" tests/noise.bin 'random:1'
check refuse "holds bzip2 content" "a bzip2 stream" tests/data.bin "bzip2:$LINE"
check refuse "holds xz content" "an xz stream" tests/data.bin "xz:$LINE"
check refuse "holds tar content" "a tar archive" tests/data.bin "tar:$LINE"
check refuse "holds zstd content" "a zstd signature" tests/data.bin 'magic:28b52ffd'
check refuse "holds 7z content" "a 7z signature" tests/data.bin 'magic:377abcaf271c'
check refuse "holds rar content" "a rar signature" tests/data.bin 'magic:526172211a07'
check refuse "holds lz4 content" "an lz4 signature" tests/data.bin 'magic:04224d18'
check refuse "holds compress content" "a compress signature" tests/data.bin 'magic:1f9d'

# The required-member check: an upload without its pytest configuration is refused.
zip_of "$WORK/bare.zip" Dockerfile 'FROM scratch' requirements.txt ''
status=0
out="$(sh "$HERE/check-package.sh" "$WORK/bare.zip" 2>&1)" || status=$?
expect refuse "missing pyproject.toml" "a missing pyproject.toml" "$status" "$out"

# The scanner itself: hooks that fail, and the binary allowlist.
mkdir "$WORK/clean" "$WORK/binary"
printf 'X = 1\n' > "$WORK/clean/a.py"
python3 -c 'import random, sys; open(sys.argv[1], "wb").write(random.Random(2).randbytes(128))' \
  "$WORK/binary/logo.png"
: > "$WORK/empty-allowlist.txt"
printf 'logo.png # the brand mark, a PNG image\n' > "$WORK/allowlist.txt"
printf 'logo.png\n' > "$WORK/allowlist-no-reason.txt"
printf 'process.exit(1);\n' > "$WORK/hook-exits-1.mjs"
printf "process.kill(process.pid, 'SIGKILL');\n" > "$WORK/hook-killed.mjs"
printf "process.stdout.write('x'.repeat(2 * 1024 * 1024));\n" > "$WORK/hook-floods.mjs"
printf 'setInterval(() => {}, 1000);\n' > "$WORK/hook-hangs.mjs"
EMPTY="$WORK/empty-allowlist.txt"

scan refuse "could not scan" "a missing secret-scan hook" "$WORK/clean" 1 "$WORK/none.mjs" "$EMPTY"
scan refuse "could not scan" "a hook that exits 1" "$WORK/clean" 1 "$WORK/hook-exits-1.mjs" "$EMPTY"
scan refuse "could not scan" "a hook stopped by a signal" "$WORK/clean" 1 "$WORK/hook-killed.mjs" "$EMPTY"
scan refuse "could not scan" "a hook whose output overflows (a spawn error)" \
  "$WORK/clean" 1 "$WORK/hook-floods.mjs" "$EMPTY"
status=0
out="$(SCAN_HOOK_TIMEOUT_MS=500 node "$HERE/scan-package.mjs" "$WORK/clean" 1 "$WORK/hook-hangs.mjs" "$EMPTY" 2>&1)" \
  || status=$?
expect refuse "could not scan" "a hook that hangs, past the timeout" "$status" "$out"
scan refuse "could not scan" "fewer files than the archive lists" "$WORK/clean" 2 "$HOOK" "$EMPTY"
scan refuse "is not text" "a binary file not on the allowlist" "$WORK/binary" 1 "$HOOK" "$EMPTY"
scan pass "Unscanned, by the binary allowlist: logo.png (the brand mark, a PNG image)" \
  "an allowlisted binary passes and is named" "$WORK/binary" 1 "$HOOK" "$WORK/allowlist.txt"
scan refuse "gives no reason" "an allowlist entry without a reason" \
  "$WORK/binary" 1 "$HOOK" "$WORK/allowlist-no-reason.txt"

# The real package from HEAD: it passes the nets and lands at the upload path, readable.
status=0
out="$(sh "$HERE/package-appstore.sh" 2>&1)" || status=$?
expect pass "wrote dist/appstore.zip" "the real package from HEAD" "$status" "$out"
mode="$(ls -l "$ROOT/dist/appstore.zip" | cut -c1-10)"
[ "$mode" = "-rw-r--r--" ] || { echo "FAIL: the upload zip has mode $mode, not -rw-r--r--"; exit 1; }
echo "ok: the upload zip is mode 0644"

echo "upload nets: all $n cases behaved"
