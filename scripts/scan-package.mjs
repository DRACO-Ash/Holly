#!/usr/bin/env node
// scan-package.mjs :: the content net for the App Store upload, run by check-package.sh.
// Usage: node scripts/scan-package.mjs <extracted-upload-dir> <expected-file-count> <hook> <binary-allowlist>
//
// It decides positively, by content: a file is scanned only when it is readable text, meaning
// strict UTF-8 (a UTF-8 byte-order mark is allowed) without control characters other than
// whitespace. That text goes to the project's secret-scan hook, so the rule list is the one
// that already guards every write. Every other file cannot be scanned and refuses the package,
// whatever its name, leading bytes or declared encoding (UTF-16 is refused too, because ASCII
// behind a UTF-16 byte-order mark decodes into meaningless characters the rules cannot read),
// unless the binary allowlist names it.
// The allowlist is read from HEAD by check-package.sh. An entry waives only the text
// requirement: it pins the file's SHA-256, so a changed file refuses; a file that is text, or
// an entry that names no packaged file, refuses; and the binary's readable runs still go to the
// hook. Allowlisted files are named on every run. Known archive and compression signatures only
// sharpen the message for a file already refused as not text.
// It fails closed, and reports a match apart from a failure to scan: the hook's block status
// (2) is "rules matched"; anything else that stops a file being judged is "could not scan".
// Either refuses the package.
// Cannot see: a secret in a shape the hook has no rule for (for example an unquoted GitHub
// token or a JWT), a secret encoded inside text (base64, a data: URI), or a secret encoded
// inside an allowlisted binary.
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
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
const HOOK_TIMEOUT_CEILING_MS = 30000;
// 30 seconds, or a shorter override for tests; never longer.
const HOOK_TIMEOUT_MS = Math.min(
  Number(process.env.SCAN_HOOK_TIMEOUT_MS) || HOOK_TIMEOUT_CEILING_MS,
  HOOK_TIMEOUT_CEILING_MS,
);
const NAME_CONTROL = /[\x00-\x1f\x7f]/;
// Control characters text does not carry: everything below space except tab, line feed,
// vertical tab, form feed and carriage return, plus DEL and the C1 range.
const TEXT_CONTROL = /[\x00-\x08\x0e-\x1f\x7f-\x9f]/;
const SHA256 = /^[0-9a-f]{64}$/;
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
const allowlisted = [];

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

// One entry per line: `<path in the upload> <sha256> # <reason>`. Blank lines and lines
// starting with # are comments. A malformed entry is an error, so nothing is allowed silently.
function readAllowlist(file) {
  const allowed = new Map();
  for (const raw of readFileSync(file, 'utf8').split('\n')) {
    const line = raw.trim();
    if (line === '' || line.startsWith('#')) continue;
    const at = line.indexOf(' # ');
    if (at < 0) throw new Error(`the allowlist entry ${JSON.stringify(line)} gives no reason`);
    const [path, sha256, extra] = line.slice(0, at).trim().split(/\s+/);
    if (!path || !SHA256.test(sha256 ?? '') || extra !== undefined) {
      throw new Error(`the allowlist entry ${JSON.stringify(line)} is not "<path> <sha256> # <reason>"`);
    }
    allowed.set(path, { sha256, reason: line.slice(at + 3).trim() });
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

// The file's text, or null when it is not readable text (strict UTF-8 only).
function asText(bytes) {
  let text;
  try {
    text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
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

function judgeAllowlisted(path, bytes, entry) {
  const shown = JSON.stringify(relative(root, path));
  const actual = createHash('sha256').update(bytes).digest('hex');
  if (actual !== entry.sha256) {
    problems.push(
      `could not scan: the allowlisted ${shown} changed (sha256 ${actual}); review it and update its entry`,
    );
  } else if (asText(bytes) !== null) {
    problems.push(`could not scan: ${shown} is text, so it needs no allowlist entry; remove it`);
  } else if (hookMatches(path, bytes.toString('utf8'))) {
    problems.push(`secret-scan rules matched in the readable runs of ${shown}`);
  } else {
    allowlisted.push(`${relative(root, path)} (${entry.reason})`);
  }
}

function judge(path, allowed) {
  const name = relative(root, path);
  const shown = JSON.stringify(name);
  const bytes = readFileSync(path);
  if (allowed.has(name)) {
    judgeAllowlisted(path, bytes, allowed.get(name));
    return;
  }
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
      : `could not scan: ${shown} is not text (strict UTF-8 without control characters)`,
  );
}

try {
  const allowed = readAllowlist(allowlistFile);
  walk(root);
  const names = new Set(files.map((path) => relative(root, path)));
  for (const name of allowed.keys()) {
    if (!names.has(name)) {
      problems.push(`could not scan: the allowlist names ${JSON.stringify(name)}, which the upload does not carry`);
    }
  }
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
const named =
  allowlisted.length > 0
    ? ` Allowlisted binaries, scanned only for readable runs: ${allowlisted.join('; ')}.`
    : '';
console.log(
  `content net: ${files.length - allowlisted.length} text files scanned, clean.${named} Cannot ` +
    "see: secret shapes outside the hook's rules, secrets encoded inside text (base64, a " +
    'data: URI), or secrets encoded inside an allowlisted binary.',
);
