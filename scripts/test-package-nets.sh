#!/bin/sh
# test-package-nets.sh :: proves the upload nets refuse what they claim to and accept a clean
# upload. Synthetic upload zips each carry one planted problem, covering every shape that once
# slipped past the nets: bracketed, control-character and hidden-byte names (a DEL extraction
# drops), a doubled slash and a backslash; archives under an upper-case or unlisted name;
# compressed streams with or without a signature (zlib, raw deflate, LZMA-alone, brotli, a
# zipapp); and ASCII behind a stray UTF-16 byte-order mark. A stand-in grep proves a failing
# name check refuses. Direct runs of the scanner prove that a hook which crashes, floods or hangs
# refuses, and that the binary allowlist waives only the text requirement for a pinned,
# unchanged binary listed once. The last cases package HEAD for real in a throwaway clone, prove
# that only a committed allowlist entry counts, and refuse committed names with a byte above
# 0x7E, an executable's among them, packaged under C.UTF-8.
# Run by verify.sh; needs git, python3, unzip and node.
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
DEL="$(printf '\177')"
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


def even_ascii(text):
    data = text.encode()
    return data if len(data) % 2 == 0 else data + b" "


ENCODERS = {
    "utf8bom": lambda t: codecs.BOM_UTF8 + t.encode(),
    "utf16": lambda t: t.encode("utf-16-le"),
    "utf16bom": lambda t: codecs.BOM_UTF16_LE + t.encode("utf-16-le"),
    "utf16bebom": lambda t: codecs.BOM_UTF16_BE + t.encode("utf-16-be"),
    "oddutf16": lambda t: b"\x01" + t.encode("utf-16-le"),
    "strayff": lambda t: b"\xff\xfe" + even_ascii(t),
    "strayfe": lambda t: b"\xfe\xff" + even_ascii(t),
    "powershell": lambda t: codecs.BOM_UTF16_LE + "Header\r\n".encode("utf-16-le")
    + even_ascii(t).decode().encode("cp1252"),
    # The text arrives with backslash escapes (for example caf\xe9), which are interpreted here.
    "latin1": lambda t: t.encode().decode("unicode_escape").encode("latin-1"),
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

sha256_of() {
  python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "$1"
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

# An upload with the required members plus the planted members given, through check-package.sh.
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
check pass "text files scanned, clean" "UTF-8 text with a byte-order mark" docs.txt 'utf8bom:plain notes'
check pass "text files scanned, clean" "a text file that begins like a bzip2 signature" \
  docs.txt 'BZh is how a bzip2 stream starts'
check refuse "secret-scan rules matched" "a key in an ordinary file" src/app/leak.py "$LINE"
check refuse "secret-scan rules matched" "a key in UTF-8 text with a byte-order mark" \
  src/app/leak.py "utf8bom:$LINE"
check refuse "secret-scan rules matched" "a key behind a bracketed name" "src/app/[leak].py" "$LINE"
check refuse "secret-scan rules matched" "a bracketed name beside a clean namesake" \
  src/app/x.py 'X = 1' "src/app/[x].py" "$LINE"
check refuse "control character" "a newline in a name" "src/app/leak${NL}b.py" "$LINE"
check refuse "control character" "a tab in a name" "src/app/leak${TAB}b.py" "$LINE"
check refuse "banned path" "an environment file by name" src/app/prod.env 'X=1'
check refuse "banned path" "an archive inside the upload" tests/data.zip 'PK'
check refuse "banned path" "an archive with an upper-case extension" tests/DATA.ZIP 'PK'
check refuse "banned path" "a zip container named as a spreadsheet" tests/report.xlsx "zip:$LINE"
check refuse "agent configuration" "a CLAUDE.md at the root" CLAUDE.md '# rules'
check refuse "agent configuration" "a lower-case claude.md, nested" frontend/claude.md '# rules'
check refuse "agent configuration" "a CLAUDE.local.md" CLAUDE.local.md '# notes'
check refuse "agent configuration" "a file under .claude/" .claude/settings.json '{}'
check refuse "agent configuration" "a nested .Claude/ directory" src/app/.Claude/agents/x.md '# agent'
check refuse "agent configuration" "a .mcp.json" .mcp.json '{}'
check pass "text files scanned, clean" "a module only named claude" src/app/services/claude.py 'X = 1'
check pass "text files scanned, clean" "a name that only ends in claude.md" src/app/myclaude.md 'notes'
check pass "text files scanned, clean" "a directory that only ends in .claude" src/app/x.claude/y.txt 'notes'
check pass "text files scanned, clean" "a claude.mdx file" src/app/claude.mdx 'notes'
check pass "text files scanned, clean" "a .claude-cache directory" src/app/.claude-cache/x.txt 'notes'
# unzip lists a DEL as it stands and extraction drops it, so each of these would land as the
# name it hides; a name extraction normalises would land under another name.
check refuse "outside printable ASCII" "a DEL hidden in CLAUDE.md" "frontend/CLAUDE${DEL}.md" '# rules'
check refuse "outside printable ASCII" "a DEL hidden in an environment file's name" \
  "src/app/prod.en${DEL}v" 'X=1'
check refuse "outside printable ASCII" "a DEL hidden in a .claude/ directory" \
  "src/.cl${DEL}aude/settings.json" '{}'
check refuse "change on extraction" "a doubled slash in a name" 'src//x.py' 'X = 1'
check refuse "backslash" "a backslash standing in for a slash" 'tests/.claude\settings.json' '{}'
check refuse "could not scan" "a symlink member" tests/link.txt 'symlink:/etc/hostname'

# Only strict UTF-8 is text. UTF-16 of any kind, and ASCII behind a stray UTF-16 byte-order
# mark, would decode into characters the rules cannot read, so it is refused.
check refuse "is not text" "a key in UTF-16LE text with a byte-order mark" tests/f.txt "utf16bom:$LINE"
check refuse "is not text" "a key in UTF-16BE text with a byte-order mark" tests/f.txt "utf16bebom:$LINE"
check refuse "is not text" "UTF-16LE text without a byte-order mark" tests/f.txt "utf16:$LINE"
check refuse "is not text" "UTF-16 text after one leading byte" tests/f.txt "oddutf16:$LINE"
check refuse "is not text" "a key behind a stray FF FE" tests/f.txt "strayff:$LINE"
check refuse "is not text" "a key behind a stray FE FF" tests/f.txt "strayfe:$LINE"
check refuse "is not text" "a PowerShell mixed UTF-16 and ANSI file" tests/f.txt "powershell:$LINE"
check refuse "is not text" "Latin-1 text, which is not valid UTF-8" tests/f.txt 'latin1:caf\xe9 = 1'

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

# A grep that fails reads as a refusal, never as "no match": a stand-in grep that errors on the
# case-blind name patterns refuses a clean upload.
mkdir "$WORK/badgrep"
printf '#!/bin/sh\ncase " $* " in *" -iE "*) exit 2 ;; esac\nexec %s "$@"\n' "$(command -v grep)" \
  > "$WORK/badgrep/grep"
chmod +x "$WORK/badgrep/grep"
zip_of "$WORK/grepfail.zip" Dockerfile 'FROM scratch' requirements.txt '' pyproject.toml ''
status=0
out="$(PATH="$WORK/badgrep:$PATH" sh "$HERE/check-package.sh" "$WORK/grepfail.zip" 2>&1)" || status=$?
expect refuse "could not check the member names" "a grep that fails on the name patterns" "$status" "$out"

# The scanner itself: hooks that fail.
mkdir "$WORK/clean"
printf 'X = 1\n' > "$WORK/clean/a.py"
: > "$WORK/empty-allowlist.txt"
EMPTY="$WORK/empty-allowlist.txt"
printf 'process.exit(1);\n' > "$WORK/hook-exits-1.mjs"
printf "process.kill(process.pid, 'SIGKILL');\n" > "$WORK/hook-killed.mjs"
printf "process.stdout.write('x'.repeat(2 * 1024 * 1024));\n" > "$WORK/hook-floods.mjs"
printf 'setInterval(() => {}, 1000);\n' > "$WORK/hook-hangs.mjs"
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

# The binary allowlist waives only the text requirement, for a pinned and unchanged binary.
mkdir "$WORK/binary" "$WORK/keyed" "$WORK/text"
python3 -c 'import random, sys; open(sys.argv[1], "wb").write(random.Random(2).randbytes(128))' \
  "$WORK/binary/logo.png"
python3 -c 'import random, sys; r = random.Random(3); open(sys.argv[1], "wb").write(r.randbytes(64) + sys.argv[2].encode() + r.randbytes(64))' \
  "$WORK/keyed/logo.png" "
$LINE
"
printf 'X = 1\n' > "$WORK/text/notes.py"
LOGO="$(sha256_of "$WORK/binary/logo.png")"
printf 'logo.png %s # the brand mark, a PNG image\n' "$LOGO" > "$WORK/allow-logo.txt"
printf 'logo.png %s # the brand mark, a PNG image\n' "$(sha256_of "$WORK/keyed/logo.png")" > "$WORK/allow-keyed.txt"
printf 'notes.py %s # not really binary\n' "$(sha256_of "$WORK/text/notes.py")" > "$WORK/allow-text.txt"
printf 'logo.png %s # the brand mark\nmodel.bin %s # a model that is not there\n' "$LOGO" "$LOGO" > "$WORK/allow-missing.txt"
printf 'logo.png %s\n' "$LOGO" > "$WORK/allow-no-reason.txt"
printf 'logo.png # the brand mark\n' > "$WORK/allow-no-hash.txt"
scan refuse "is not text" "a binary not on the allowlist" "$WORK/binary" 1 "$HOOK" "$EMPTY"
scan pass "Allowlisted binaries, scanned only for readable runs: logo.png (the brand mark, a PNG image)" \
  "a pinned binary passes and is named" "$WORK/binary" 1 "$HOOK" "$WORK/allow-logo.txt"
mkdir "$WORK/mixed"
cp "$WORK/binary/logo.png" "$WORK/mixed/logo.png"
printf '%s\n' "$LINE" > "$WORK/mixed/leak.py"
scan refuse "secret-scan rules matched" "a key in a text file beside a pinned binary" \
  "$WORK/mixed" 2 "$HOOK" "$WORK/allow-logo.txt"
scan refuse "changed" "an allowlisted binary whose content changed" "$WORK/keyed" 1 "$HOOK" "$WORK/allow-logo.txt"
scan refuse "rules matched in the readable runs" "a key in an allowlisted binary's readable runs" \
  "$WORK/keyed" 1 "$HOOK" "$WORK/allow-keyed.txt"
scan refuse "needs no allowlist entry" "an allowlisted file that is text" "$WORK/text" 1 "$HOOK" "$WORK/allow-text.txt"
scan refuse "does not carry" "an allowlist entry for a file the upload lacks" \
  "$WORK/binary" 1 "$HOOK" "$WORK/allow-missing.txt"
scan refuse "gives no reason" "an allowlist entry without a reason" "$WORK/binary" 1 "$HOOK" "$WORK/allow-no-reason.txt"
scan refuse "is not" "an allowlist entry without a hash" "$WORK/binary" 1 "$HOOK" "$WORK/allow-no-hash.txt"
# A path listed twice refuses, even though its last entry pins the right hash and would pass alone.
printf 'logo.png %s # the brand mark\nlogo.png %s # the brand mark, listed again\n' \
  "$(sha256_of "$WORK/keyed/logo.png")" "$LOGO" > "$WORK/allow-twice.txt"
scan refuse "more than once" "an allowlist that lists a path twice" "$WORK/binary" 1 "$HOOK" "$WORK/allow-twice.txt"

# The real package from HEAD, in a throwaway clone carrying this working tree's nets, so the
# loop never rewrites this repository's dist/appstore.zip.
git clone -q "$ROOT" "$WORK/repo"
cp "$HERE/package-appstore.sh" "$HERE/check-package.sh" "$HERE/scan-package.mjs" "$WORK/repo/scripts/"
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" 2>&1)" || status=$?
expect pass "wrote dist/appstore.zip" "the real package from HEAD" "$status" "$out"
mode="$(ls -l "$WORK/repo/dist/appstore.zip" | cut -c1-10)"
[ "$mode" = "-rw-r--r--" ] || { echo "FAIL: the upload zip has mode $mode, not -rw-r--r--"; exit 1; }
echo "ok: the upload zip is mode 0644"

# Only a committed allowlist entry counts: the same entry refuses while it sits in the working
# tree alone, and passes once committed.
mkdir -p "$WORK/repo/tests/fixtures"
python3 -c 'import random, sys; open(sys.argv[1], "wb").write(random.Random(4).randbytes(128))' \
  "$WORK/repo/tests/fixtures/logo.dat"
commit_in_clone() {  # $1: path to commit, $2: message
  git -C "$WORK/repo" add -- "$1"
  git -C "$WORK/repo" -c user.name=test -c user.email=test@localhost -c commit.gpgsign=false \
    commit -q -m "$2"
}
commit_in_clone tests/fixtures/logo.dat "a binary fixture"
printf 'tests/fixtures/logo.dat %s # a fixture image\n' "$(sha256_of "$WORK/repo/tests/fixtures/logo.dat")" \
  >> "$WORK/repo/scripts/upload-binaries.txt"
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" 2>&1)" || status=$?
expect refuse "is not text" "an allowlist entry that is not committed" "$status" "$out"
commit_in_clone scripts/upload-binaries.txt "allowlist the fixture"
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" 2>&1)" || status=$?
expect pass "Allowlisted binaries, scanned only for readable runs: tests/fixtures/logo.dat (a fixture image)" \
  "the same entry once committed" "$status" "$out"

# A committed name with a byte above 0x7E, which git archive writes as it stands and extraction
# would change, is refused before it can land under another name.
high="tests/CLAUDE.local$(printf '\377').md"
printf '# notes\n' > "$WORK/repo/$high"
commit_in_clone "$high" "a name with a byte above 0x7E"
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" 2>&1)" || status=$?
expect refuse "outside printable ASCII" "a committed name with a byte above 0x7E" "$status" "$out"
rm -- "$WORK/repo/$high"
commit_in_clone "$high" "drop the name with a byte above 0x7E"

# The same for an executable, which git archive marks as made on Unix, so unzip keeps its byte,
# packaged under C.UTF-8, where grep sees an invalid byte only if the net reads names in C.
latin="tests/caf$(printf '\351').py"
printf 'X = 1\n' > "$WORK/repo/$latin"
chmod +x "$WORK/repo/$latin"
commit_in_clone "$latin" "an executable with a byte above 0x7E"
status=0
out="$(LC_ALL=C.UTF-8 sh "$WORK/repo/scripts/package-appstore.sh" 2>&1)" || status=$?
expect refuse "outside printable ASCII" "an executable with a byte above 0x7E, under C.UTF-8" \
  "$status" "$out"

echo "upload nets: all $n cases behaved"
