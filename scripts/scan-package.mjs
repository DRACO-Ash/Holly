#!/usr/bin/env node
// scan-package.mjs :: the content net for the App Store upload, run by check-package.sh.
// Usage: node scripts/scan-package.mjs <extracted-upload-dir> <expected-file-count> <hook> <binary-allowlist>
//
// It decides positively, by content: a file is scanned only when it is readable text, meaning
// strict UTF-8, or UTF-16 that opens with a byte-order mark and decodes strictly, in either
// case without control characters other than whitespace. That text goes to the project's
// secret-scan hook, so the rule list is the one that already guards every write. Every other
// file cannot be scanned and refuses the package, whatever its name or leading bytes, unless
// the committed binary allowlist names it with a reason; allowlisted files are named as
// unscanned on every run. Known archive and compression signatures only sharpen the message
// for a file already refused as not text.
// It fails closed, and reports a match apart from a failure to scan: the hook's block status
// (2) is "rules matched"; anything else that stops a file being judged (not text, a missing
// hook, any other status or a signal, a read or spawn error, a timeout, a symlink or special
// file, a control character in a name, an allowlist entry without a reason, or a file count
// that differs from the archive's) is "could not scan". Either refuses the package.
// Cannot see: a secret in a shape the hook has no rule for (for example an unquoted GitHub
// token or a JWT), a secret encoded inside text (base64, a data: URI), or anything inside an
// allowlisted binary.
import { spawnSync } from 'node:child_process';
import { existsSync, lstatSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';

const [root, expectedArg, hook, allowlistFile] = process.argv.slice(2);
if (!root || !expectedArg || !hook || !allowlistFile) {
  console.error(
    'usage: scan-package.mjs <extracted-upload-dir> <expected-file-count> <hook> <binary-allowlist>',
  );
  process.exit(1);
}
if (!existsSync(hook)) {
  console.error(`content net: could not scan: the secret-scan hook is missing at ${hook}`);
  process.exit(1);
}

const HOOK_BLOCKED = 2; // the hook's documented exit status for a match
// 30 seconds unless overridden; a shorter timeout only refuses sooner.
const HOOK_TIMEOUT_MS = Number(process.env.SCAN_HOOK_TIMEOUT_MS) || 30000;
const NAME_CONTROL = /[\x00-\x1f\x7f]/;
// Control characters text does not carry: everything below space except tab, line feed,
// vertical tab, form feed and carriage return, plus DEL and the C1 range.
const TEXT_CONTROL = /[\x00-\x08\x0e-\x1f\x7f-\x9f]/;
// [kind, byte offset, leading bytes]: only to name the format in the refusal message.
const SIGNATURES = [
  ['zip', 0, [0x50, 0x4b, 0x03, 0x04]],
  ['zip', 0, [0x50, 0x4b, 0x05, 0x06]],
  ['zip', 0, [0x50, 0x4b, 0x07, 0x08]],
  ['gzip', 0, [0x1f, 0x8b]],
  ['bzip2', 0, [0x42, 0x5a, 0x68]],
  ['xz', 0, [0xfd, 0x37, 0x7a, 0x58, 0x5a, 0x00]],
  ['zstd', 0, [0x28, 0xb5, 0x2f, 0xfd]],
  ['7z', 0, [0x37, 0x7a, 0xbc, 0xaf, 0x27, 0x1c]],
  ['rar', 0, [0x52, 0x61, 0x72, 0x21, 0x1a, 0x07]],
  ['lz4', 0, [0x04, 0x22, 0x4d, 0x18]],
  ['compress', 0, [0x1f, 0x9d]],
  ['tar', 257, [0x75, 0x73, 0x74, 0x61, 0x72]],
];
const problems = [];
const files = [];
const unscanned = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const shown = JSON.stringify(relative(root, path));
    if (NAME_CONTROL.test(name)) problems.push(`could not scan: a control character in ${shown}`);
    const stats = lstatSync(path);
    if (stats.isDirectory()) walk(path);
    else if (stats.isFile()) files.push(path);
    else problems.push(`could not scan: ${shown} is not a regular file`);
  }
}

// One entry per line: `<path in the upload> # <reason>`. Blank lines and lines starting with #
// are comments. An entry without a reason is an error, so nothing is allowlisted silently.
function readAllowlist(file) {
  const allowed = new Map();
  for (const raw of readFileSync(file, 'utf8').split('\n')) {
    const line = raw.trim();
    if (line === '' || line.startsWith('#')) continue;
    const at = line.indexOf(' # ');
    if (at < 0) throw new Error(`the allowlist entry ${JSON.stringify(line)} gives no reason`);
    allowed.set(line.slice(0, at).trim(), line.slice(at + 3).trim());
  }
  return allowed;
}

function containerKind(bytes) {
  for (const [kind, offset, magic] of SIGNATURES) {
    const end = offset + magic.length;
    if (bytes.length >= end && magic.every((value, index) => bytes[offset + index] === value)) {
      return kind;
    }
  }
  return null;
}

// The file's text, or null when it is not readable text.
function asText(bytes) {
  let encoding = 'utf-8';
  if (bytes[0] === 0xff && bytes[1] === 0xfe) encoding = 'utf-16le';
  else if (bytes[0] === 0xfe && bytes[1] === 0xff) encoding = 'utf-16be';
  let text;
  try {
    text = new TextDecoder(encoding, { fatal: true }).decode(bytes);
  } catch {
    return null;
  }
  return TEXT_CONTROL.test(text) ? null : text;
}

// True on a rule match. Throws when the hook could not judge the content at all, including a
// hook that hangs: the timeout turns it into an error rather than a stalled package.
function hookMatches(path, content) {
  const payload = JSON.stringify({ tool_name: 'Write', tool_input: { file_path: path, content } });
  const result = spawnSync(process.execPath, [hook], {
    input: payload,
    encoding: 'utf8',
    timeout: HOOK_TIMEOUT_MS,
  });
  if (result.error) throw result.error;
  if (result.signal) throw new Error(`the hook was stopped by ${result.signal} on ${path}`);
  if (result.status === HOOK_BLOCKED) return true;
  if (result.status !== 0) throw new Error(`the hook exited ${result.status} on ${path}`);
  return false;
}

function judge(path, allowed) {
  const name = relative(root, path);
  const shown = JSON.stringify(name);
  if (allowed.has(name)) {
    unscanned.push(`${name} (${allowed.get(name)})`);
    return;
  }
  const bytes = readFileSync(path);
  // Text first, so a text file that happens to begin like a signature is still scanned.
  const text = asText(bytes);
  if (text !== null) {
    if (hookMatches(path, text)) problems.push(`secret-scan rules matched in ${shown}`);
    return;
  }
  const kind = containerKind(bytes);
  problems.push(
    kind
      ? `could not scan: ${shown} holds ${kind} content, which hides its text`
      : `could not scan: ${shown} is not text (strict UTF-8, or UTF-16 with a byte-order mark)`,
  );
}

try {
  const allowed = readAllowlist(allowlistFile);
  walk(root);
  for (const path of files) judge(path, allowed);
} catch (error) {
  problems.push(`could not scan: ${error.message}`);
}

const expected = Number(expectedArg);
if (files.length !== expected) {
  problems.push(`could not scan: found ${files.length} files but the archive lists ${expected}`);
}

if (problems.length > 0) {
  for (const problem of problems) console.error(`content net: ${problem}`);
  process.exit(1);
}
const named = unscanned.length > 0 ? ` Unscanned, by the binary allowlist: ${unscanned.join('; ')}.` : '';
console.log(
  `content net: ${files.length - unscanned.length} text files scanned, clean.${named} Cannot ` +
    "see: secret shapes outside the hook's rules, secrets encoded inside text (base64, a " +
    'data: URI), or anything inside an allowlisted binary.',
);
