#!/usr/bin/env node
// scan-package.mjs :: the content net for the App Store upload, run by check-package.sh.
// Usage: node scripts/scan-package.mjs <extracted-upload-dir> <expected-file-count> <hook>
//
// Every regular file in the extracted upload is decoded as UTF-8, and also as UTF-16LE when it
// holds a NUL byte, and passed to the project's secret-scan hook, so the rule list is the one
// that already guards every write. It fails closed, and reports a match apart from a failure to
// scan: the hook's block status (2) is "rules matched"; a missing hook, any other non-zero
// status, a read or spawn error, a symlink or special file, a control character in a name, or a
// file count that differs from the archive's is "could not scan". Either refuses the package.
// Cannot see: a secret in a shape the hook has no rule for (for example an unquoted GitHub
// token or a JWT), or in an encoding other than UTF-8 and UTF-16LE.
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
const CONTROL = /[\x00-\x1f\x7f]/;
const problems = [];
const files = [];

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const shown = JSON.stringify(relative(root, path));
    if (CONTROL.test(name)) problems.push(`a control character in a name: ${shown}`);
    const stats = lstatSync(path);
    if (stats.isDirectory()) walk(path);
    else if (stats.isFile()) files.push(path);
    else problems.push(`not a regular file: ${shown}`);
  }
}

// True on a rule match. Throws when the hook could not judge the content at all.
function hookMatches(path, content) {
  const payload = JSON.stringify({ tool_name: 'Write', tool_input: { file_path: path, content } });
  const result = spawnSync(process.execPath, [hook], { input: payload, encoding: 'utf8' });
  if (result.error) throw result.error;
  if (result.status === HOOK_BLOCKED) return true;
  if (result.status !== 0) throw new Error(`the hook exited ${result.status} on ${path}`);
  return false;
}

try {
  walk(root);
  for (const path of files) {
    const bytes = readFileSync(path);
    const views = [bytes.toString('utf8')];
    if (bytes.includes(0)) views.push(bytes.toString('utf16le'));
    if (views.some((text) => hookMatches(path, text))) {
      problems.push(`secret-scan rules matched in ${JSON.stringify(relative(root, path))}`);
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
    "hook's rules, or encodings other than UTF-8 and UTF-16LE.",
);
