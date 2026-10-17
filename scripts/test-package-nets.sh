#!/bin/sh
# test-package-nets.sh :: proves the upload nets refuse what they claim to and accept a clean
# upload. Synthetic upload zips each carry one planted problem, covering every shape that once
# slipped past the nets: bracketed, control-character and hidden-byte names (a DEL extraction
# drops), a doubled slash, a VMS version suffix and a backslash; archives under an upper-case
# or unlisted name; compressed streams with or without a signature (zlib, raw deflate,
# LZMA-alone, brotli, a zipapp); and ASCII behind a stray UTF-16 byte-order mark. A stand-in
# grep proves a failing name check refuses. Direct runs of the scanner prove that a hook which
# crashes, floods or hangs refuses, and that the binary allowlist waives only the text
# requirement for a pinned, unchanged binary listed once. Then cases package HEAD for real, as
# rehearsals outside dist/, in a throwaway clone, prove that only a committed allowlist entry
# counts, and refuse committed names with a byte above 0x7E, an executable's among them,
# packaged under C.UTF-8. The last cases, in a second clone, prove that packaging for upload
# refuses unless the last verdict from each review in the committed record is a PASS on a commit
# whose upload and packaging are unchanged, whatever git's index, local filters and attributes or
# a commit landing meanwhile would make of it, and that a rehearsal needs no record. Run by
# verify.sh; needs git, python3, unzip and node.
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
check refuse "change on extraction" "a VMS version suffix on CLAUDE.md" 'frontend/CLAUDE.md;1' '# rules'
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
# loop never writes this repository's dist/. A rehearsal writes where it is told, outside dist/.
git clone -q "$ROOT" "$WORK/repo"
cp "$HERE/package-appstore.sh" "$HERE/check-package.sh" "$HERE/scan-package.mjs" "$WORK/repo/scripts/"
REH="$WORK/rehearsal.zip"
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" --rehearsal "$REH" 2>&1)" || status=$?
expect pass "a REHEARSAL, never the upload" "the real package from HEAD" "$status" "$out"
mode="$(ls -l "$REH" | cut -c1-10)"
[ "$mode" = "-rw-r--r--" ] || { echo "FAIL: the rehearsal zip has mode $mode, not -rw-r--r--"; exit 1; }
echo "ok: the rehearsal zip is mode 0644"

# dist/ holds only checked uploads: a rehearsal aimed into it refuses, and every run, a mistyped
# one included, first removes the last upload zip.
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" --rehearsal "$WORK/repo/dist/rehearsal.zip" 2>&1)" \
  || status=$?
expect refuse "never writes into dist/" "a rehearsal aimed into dist/" "$status" "$out"
printf 'stale\n' > "$WORK/repo/dist/appstore.zip"
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" --rehersal "$REH" 2>&1)" || status=$?
expect refuse "usage:" "a mistyped option" "$status" "$out"
[ ! -e "$WORK/repo/dist/appstore.zip" ] || { echo "FAIL: a mistyped run left dist/appstore.zip"; exit 1; }
echo "ok: a mistyped run removes the last upload zip"

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
out="$(sh "$WORK/repo/scripts/package-appstore.sh" --rehearsal "$REH" 2>&1)" || status=$?
expect refuse "is not text" "an allowlist entry that is not committed" "$status" "$out"
commit_in_clone scripts/upload-binaries.txt "allowlist the fixture"
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" --rehearsal "$REH" 2>&1)" || status=$?
expect pass "Allowlisted binaries, scanned only for readable runs: tests/fixtures/logo.dat (a fixture image)" \
  "the same entry once committed" "$status" "$out"

# A committed name with a byte above 0x7E, which git archive writes as it stands and extraction
# would change, is refused before it can land under another name.
high="tests/CLAUDE.local$(printf '\377').md"
printf '# notes\n' > "$WORK/repo/$high"
commit_in_clone "$high" "a name with a byte above 0x7E"
status=0
out="$(sh "$WORK/repo/scripts/package-appstore.sh" --rehearsal "$REH" 2>&1)" || status=$?
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
out="$(LC_ALL=C.UTF-8 sh "$WORK/repo/scripts/package-appstore.sh" --rehearsal "$REH" 2>&1)" || status=$?
expect refuse "outside printable ASCII" "an executable with a byte above 0x7E, under C.UTF-8" \
  "$status" "$out"

# The review record, in a second clone that commits this working tree's packaging tools without
# a record, then the version 9.10, a later 9.11 and 9.10 again: the bump that counts is the last
# commit that set the version. Each case commits a record on top of it and packages for upload.
git clone -q "$ROOT" "$WORK/rec"
cp "$HERE/package-appstore.sh" "$HERE/check-package.sh" "$HERE/scan-package.mjs" \
  "$HERE/check-reviews.sh" "$WORK/rec/scripts/"
rm -f -- "$WORK/rec/scripts/upload-record.txt"
rec_git() { git -C "$WORK/rec" -c user.name=test -c user.email=test@localhost -c commit.gpgsign=false "$@"; }
rec_commit() {  # $1: message, then the paths to commit
  message="$1"
  shift
  git -C "$WORK/rec" add -A -- "$@"
  rec_git commit -q --allow-empty -m "$message"
}
set_version() {  # $1: the version to commit
  sed "s/^__version__ = .*/__version__ = \"$1\"/" "$WORK/rec/src/app/__init__.py" > "$WORK/version.py"
  cp "$WORK/version.py" "$WORK/rec/src/app/__init__.py"
  rec_commit "version $1" src/app/__init__.py
}
rec_commit "the packaging tools under test, and no record" scripts
set_version 9.10
early="$(git -C "$WORK/rec" rev-parse HEAD)"
set_version 9.11
set_version 9.10
bump="$(git -C "$WORK/rec" rev-parse HEAD)"
set_record() {  # the record's lines, committed on top of the bump
  git -C "$WORK/rec" reset -q --hard "$bump"
  git -C "$WORK/rec" clean -fdq
  printf '%s\n' "$@" > "$WORK/rec/scripts/upload-record.txt"
  rec_commit "a review record" scripts/upload-record.txt
}
package_rec() {  # $1: pass or refuse, $2: text the output must hold, $3: label, then options
  expected="$1"
  fragment="$2"
  label="$3"
  shift 3
  status=0
  out="$(sh "$WORK/rec/scripts/package-appstore.sh" "$@" 2>&1)" || status=$?
  expect "$expected" "$fragment" "$label" "$status" "$out"
}
no_upload_zip() {  # $1: what must not have left an upload zip
  [ ! -e "$WORK/rec/dist/appstore.zip" ] || { echo "FAIL: $1 left dist/appstore.zip"; exit 1; }
  echo "ok: $1 leaves no upload zip"
}
head_of_rec() { git -C "$WORK/rec" rev-parse HEAD; }
E="review engineering-reviewer"
S="review security-reviewer"

package_rec pass "a REHEARSAL, never the upload" "a rehearsal, which needs no record" \
  --rehearsal "$WORK/rec-rehearsal.zip"
no_upload_zip "a rehearsal"
package_rec refuse "upload-record.txt is not committed at" "an upload without a record"
status=0
out="$(sh "$WORK/rec/scripts/check-reviews.sh" "$bump" 2>&1)" || status=$?
expect refuse "needs the commit to package and its upload paths" "the review check without upload paths" \
  "$status" "$out"

# The last verdict from each reviewer decides, so a FAIL that a later PASS follows does not
# count; comments, blank lines and tabs are fine. The PASS holds on the commit that records it,
# which leaves the upload alone.
TAB="$(printf '\t')"
set_record "# reviews of 9.10" "" "$E PASS $bump" "$S FAIL $bump # the first round" \
  "review${TAB}security-reviewer${TAB}PASS${TAB}$bump # after its fixes"
package_rec pass "wrote dist/appstore.zip from $(head_of_rec)" "both reviews passed, the last verdict deciding"
mode="$(ls -l "$WORK/rec/dist/appstore.zip" | cut -c1-10)"
[ "$mode" = "-rw-r--r--" ] || { echo "FAIL: the upload zip has mode $mode, not -rw-r--r--"; exit 1; }
echo "ok: the upload zip is mode 0644"
# Only the committed record counts, and a refusal leaves no upload zip.
git -C "$WORK/rec" reset -q --hard "$bump"
printf '%s\n' "$E PASS $bump" "$S PASS $bump" > "$WORK/rec/scripts/upload-record.txt"
package_rec refuse "is not committed at" "a record that is not committed"
no_upload_zip "a refusal"
set_record "$E PASS $bump"
package_rec refuse "holds no security-reviewer verdict" "only one review recorded"
set_record "$E PASS $bump" "$S PASS $bump" "$E FAIL $bump # a finding after the pass"
package_rec refuse "the last engineering-reviewer verdict, line 3, is FAIL" "a FAIL after a PASS"
# A FAIL counts whatever commit it names: recorded last against an older tree, it still refuses.
set_record "$E PASS $bump" "$S PASS $bump" "$S FAIL $early # a finding against an older tree"
package_rec refuse "the last security-reviewer verdict, line 3, is FAIL" "a FAIL recorded last against an older commit"
# The first 9.10 carries the same upload as the bump, but comes before it.
set_record "$E PASS $early" "$S PASS $early"
package_rec refuse "comes before" "verdicts on a commit before the bump, with the same upload"
side="$(rec_git commit-tree -p "$bump" -m "a side commit" "$bump^{tree}")"
set_record "$E PASS $side" "$S PASS $side"
package_rec refuse "which is not in" "verdicts on a commit outside the packaged commit's history"
set_record "$E PASS 1234567890abcdef1234567890abcdef12345678" "$S PASS $bump"
package_rec refuse "not a commit in this repository" "a verdict on an unknown commit"

# A line that is not a well-formed verdict refuses the whole record.
set_record "$E PASS $bump" "$S PASS ${bump%?}"
package_rec refuse "line 2 is not" "a commit id one character short"
set_record "$E pass $bump" "$S PASS $bump"
package_rec refuse "line 1 is not" "a verdict in lower case"
set_record "$E PASS HEAD~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0~0" "$S PASS $bump"
package_rec refuse "line 1 is not" "a revision expression 40 characters long"
set_record "$E PASS $bump reviewed" "$S PASS $bump"
package_rec refuse "line 1 is not" "a trailing word that is not a note"
set_record "verdict engineering-reviewer PASS $bump" "$S PASS $bump"
package_rec refuse "line 1 is not" "a line that is not a review"
set_record "$E PASS $bump" "# a note$(printf '\r')$S FAIL $bump" "$S PASS $bump"
package_rec refuse "line 2 holds a byte outside printable ASCII" "a carriage return that hides a verdict"

# The version must be readable at the commit packaged.
set_record "$E PASS $bump" "$S PASS $bump"
sed '/^__version__ = /d' "$WORK/rec/src/app/__init__.py" > "$WORK/version.py"
cp "$WORK/version.py" "$WORK/rec/src/app/__init__.py"
rec_commit "no version" src/app/__init__.py
package_rec refuse "no __version__" "a commit without a version"

# A PASS against a tree that has since moved refuses, until the moved tree is reviewed.
set_record "$E PASS $bump" "$S PASS $bump"
printf '\nA later line.\n' >> "$WORK/rec/README.md"
rec_commit "the upload moves on" README.md
package_rec refuse "has changed since (README.md)" "an upload changed after its reviews"
moved="$(head_of_rec)"
printf '%s\n' "$E PASS $moved" "$S PASS $moved" >> "$WORK/rec/scripts/upload-record.txt"
rec_commit "the reviews of the move" scripts/upload-record.txt
package_rec pass "security-reviewer: PASS at $(printf '%.7s' "$moved")" "the moved upload, reviewed"

# Every packaging tool is part of what the reviews passed: a change committed after them refuses,
# and so does an edit that is not committed. The packager's change drops tests from its path list;
# .gitattributes is new.
change_tool() {  # $1: the tool to change, so that it still runs
  case "$1" in
    scripts/package-appstore.sh)
      sed 's/ src tests frontend"$/ src frontend"/' "$WORK/rec/$1" > "$WORK/tool.tmp"
      cmp -s "$WORK/tool.tmp" "$WORK/rec/$1" && { echo "FAIL: the path list did not change"; exit 1; }
      cp "$WORK/tool.tmp" "$WORK/rec/$1" ;;
    .gitattributes) printf 'tests export-ignore\n' >> "$WORK/rec/$1" ;;
    *.mjs) printf '// a later comment\n' >> "$WORK/rec/$1" ;;
    *) printf '# a later comment\n' >> "$WORK/rec/$1" ;;
  esac
}
for tool in scripts/check-reviews.sh scripts/package-appstore.sh scripts/check-package.sh \
  scripts/scan-package.mjs scripts/upload-binaries.txt .claude/hooks/secret-scan.mjs .gitattributes; do
  set_record "$E PASS $bump" "$S PASS $bump"
  change_tool "$tool"
  rec_commit "$tool moves on" "$tool"
  package_rec refuse "has changed since ($tool)" "$tool, changed after the reviews"
  set_record "$E PASS $bump" "$S PASS $bump"
  change_tool "$tool"
  package_rec refuse "differ from $(printf '%.7s' "$(head_of_rec)") ($tool)" "$tool, edited but not committed"
done
# An edit that git's index is told to ignore still refuses: the tools are compared by content.
set_record "$E PASS $bump" "$S PASS $bump"
git -C "$WORK/rec" update-index --skip-worktree scripts/check-package.sh
printf '# hidden from git status\n' >> "$WORK/rec/scripts/check-package.sh"
[ -z "$(git -C "$WORK/rec" status --porcelain -- scripts/check-package.sh)" ] \
  || { echo "FAIL: the premise failed: git status shows the edit"; exit 1; }
package_rec refuse "differ from" "a tool edit that skip-worktree hides from git status"
git -C "$WORK/rec" update-index --no-skip-worktree scripts/check-package.sh

# The zip must hold the committed files byte for byte, whatever git's local filters and
# attributes would make of them, and the nets still judge a reviewed upload.
set_record "$E PASS $bump" "$S PASS $bump"
git -C "$WORK/rec" config filter.swap.smudge "sed s/Holly/H0lly/"
printf 'README.md filter=swap\n' > "$WORK/rec/.git/info/attributes"
package_rec refuse "does not hold the files of" "a local smudge filter that rewrites a packaged file"
printf 'tests export-ignore\n' > "$WORK/rec/.git/info/attributes"
package_rec refuse "does not hold the files of" "a local attribute that drops packaged files"
: > "$WORK/rec/.git/info/attributes"
git -C "$WORK/rec" config --unset filter.swap.smudge
git -C "$WORK/rec" reset -q --hard "$bump"
printf '%s\n' "$LINE" > "$WORK/rec/src/app/leak.py"
rec_commit "a key in the source" src/app/leak.py
keyed="$(head_of_rec)"
printf '%s\n' "$E PASS $keyed" "$S PASS $keyed" > "$WORK/rec/scripts/upload-record.txt"
rec_commit "the reviews of the keyed tree" scripts/upload-record.txt
package_rec refuse "secret-scan rules matched" "a reviewed upload that holds a key"
no_upload_zip "a reviewed upload the nets refuse"

# HEAD is resolved once: a commit landing while packaging refuses, never slips in. A stand-in git
# commits on its way into git archive.
set_record "$E PASS $bump" "$S PASS $bump"
mkdir "$WORK/movegit"
printf '#!/bin/sh\ncase " $* " in *" archive "*) "%s" -C "%s" -c user.name=test -c user.email=test@localhost -c commit.gpgsign=false commit -q --allow-empty -m moved ;; esac\nexec "%s" "$@"\n' \
  "$(command -v git)" "$WORK/rec" "$(command -v git)" > "$WORK/movegit/git"
chmod +x "$WORK/movegit/git"
status=0
out="$(PATH="$WORK/movegit:$PATH" sh "$WORK/rec/scripts/package-appstore.sh" 2>&1)" || status=$?
expect refuse "HEAD moved from" "a commit landing while packaging" "$status" "$out"
no_upload_zip "a commit landing while packaging"

echo "upload nets: all $n cases behaved"
