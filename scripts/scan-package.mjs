#!/usr/bin/env node
// scan-package.mjs :: the content net for the App Store upload, run by check-package.sh.
// Usage: node scripts/scan-package.mjs <extracted-upload-dir> <expected-file-count> <hook>
//
// Every regular file in the extracted upload is decoded as UTF-8 and, when it holds a NUL byte,
// as UTF-16 in both byte orders at both alignments, and passed to the project's secret-scan hook,
// so the rule list is the one that already guards every write. What to read is decided by
// content, never by name: a file whose leading bytes mark an archive or a compressed stream
// (zip and its family such as xlsx and jar, gzip, bzip2, xz, zstd, 7z, rar, lz4, compress, tar)
// hides its text, so it cannot be scanned and is refused, whatever it is called.
// It fails closed, and reports a match apart from a failure to scan: the hook's block status
// (2) is "rules matched"; a missing hook, any other status or a signal, a read or spawn error, a
// symlink or special file, a control character in a name, archive or compressed content, or a
// file count that differs from the archive's is "could not scan". Either refuses the package.
// Cannot see: a secret in a shape the hook has no rule for (for example an unquoted GitHub
// token or a JWT); in an encoding other than UTF-8 and UTF-16; or in a compressed stream
// embedded inside another format, such as a PDF, a Parquet file or an image.
import { spawnSync } from 'node:child_process';
import { existsSync, lstatSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative } from 'node:path';

const [root, expectedArg, hook] = process.argv.slice(2);
if (!root || !expectedArg || !hook) {
  console.error('usage: scan-package.mjs <extracted-upload-dir> <expected-file-count> <hook>');
  process.exit(1);
}
if (!existsSync(hook)) {
  console.error(`content net: could not scan: the secret-scan hook is missing at ${hook}`);
  process.exit(1);
}

const HOOK_BLOCKED = 2; // the hook's documented exit status for a match
const HOOK_TIMEOUT_MS = 30000;
const CONTROL = /[\x00-\x1f\x7f]/;
// [kind, byte offset, leading bytes] for archives and compressed streams.
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

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const shown = JSON.stringify(relative(root, path));
    if (CONTROL.test(name)) problems.push(`could not scan: a control character in ${shown}`);
    const stats = lstatSync(path);
    if (stats.isDirectory()) walk(path);
    else if (stats.isFile()) files.push(path);
    else problems.push(`could not scan: ${shown} is not a regular file`);
  }
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

function utf16BigEndian(bytes) {
  const even = Buffer.from(bytes.subarray(0, bytes.length - (bytes.length % 2)));
  return even.swap16().toString('utf16le');
}

function textViews(bytes) {
  const views = [bytes.toString('utf8')];
  if (bytes.includes(0)) {
    const shifted = bytes.subarray(1);
    views.push(bytes.toString('utf16le'), shifted.toString('utf16le'));
    views.push(utf16BigEndian(bytes), utf16BigEndian(shifted));
  }
  return views;
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

try {
  walk(root);
  for (const path of files) {
    const shown = JSON.stringify(relative(root, path));
    const bytes = readFileSync(path);
    const kind = containerKind(bytes);
    if (kind) {
      problems.push(`could not scan: ${shown} holds ${kind} content, which hides its text`);
    } else if (textViews(bytes).some((text) => hookMatches(path, text))) {
      problems.push(`secret-scan rules matched in ${shown}`);
    }
  }
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
console.log(
  `content net: ${files.length} files scanned, clean. Cannot see: secret shapes outside the ` +
    "hook's rules, encodings other than UTF-8 and UTF-16, or compressed streams embedded " +
    'inside other formats (a PDF, a Parquet file, an image).',
);
