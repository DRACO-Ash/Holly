#!/usr/bin/env node
// css-duplicates.mjs :: refuses a selector written twice in the same scope of the dashboard
// stylesheet (SonarQube css:S4666), which V0.16's upload failed the platform's Code Quality stage
// on. Run by verify.sh. Usage: node scripts/css-duplicates.mjs [path to a stylesheet]
//
// A scope is the top level of the sheet or the inside of one at-rule block (@media, @supports and
// the like); the same selector in two different @media blocks is not a duplicate, as in Sonar.
// A selector list is compared as stylelint's no-duplicate-selectors (the base of css:S4666)
// compares it: split on its top-level commas, each part with its whitespace collapsed and its
// combinators (>, +, ~) spaced alike, the parts in any order. Comments and strings are read so
// that a brace inside either is not taken for a block. A @keyframes block's steps (0%, 50%) are
// not selectors and are skipped. It fails closed: a sheet it cannot read, or whose braces do not
// balance, fails.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const path =
  process.argv[2] ?? fileURLToPath(new URL('../frontend/src/styles/tokens.css', import.meta.url));

// The sheet with each comment made spaces and each string's braces made spaces, so line numbers
// and positions stay as written.
function blanked(text) {
  let out = '';
  let i = 0;
  while (i < text.length) {
    if (text.startsWith('/*', i)) {
      const end = text.indexOf('*/', i + 2);
      const stop = end === -1 ? text.length : end + 2;
      out += text.slice(i, stop).replace(/[^\n]/g, ' ');
      i = stop;
    } else if (text[i] === '\\') {
      // An escaped character, a quote among them, is the character itself, not a string's start.
      out += text.slice(i, i + 2);
      i += 2;
    } else if (text[i] === '"' || text[i] === "'") {
      const quote = text[i];
      let j = i + 1;
      while (j < text.length && text[j] !== quote && text[j] !== '\n') j += text[j] === '\\' ? 2 : 1;
      out += text.slice(i, j + 1).replace(/[{};]/g, ' ');
      i = j + 1;
    } else {
      out += text[i];
      i += 1;
    }
  }
  return out;
}

// The key a selector list is compared by. Commas and combinators inside brackets or parentheses
// (an attribute value, :is(a, b)) are part of their selector, not the list's; so is anything in a
// quoted string, and a character after a backslash. Not normalised, so a duplicate written either
// way is missed: the order or spacing inside a pseudo-class's brackets (:not(.a, .b) and
// :not(.b,.a)) and the spacing of an attribute's operator ([x~="y"] and [x ~= "y"]). And an
// escaped space followed by a space (.a\\  .b) is read as one, so it can be reported as a
// duplicate of .a\\ .b: a false alarm, never a miss.
export function selectorKey(list) {
  const parts = [];
  let depth = 0;
  let quote = null;
  let part = '';
  for (let i = 0; i < list.length; i += 1) {
    const char = list[i];
    if (char === '\\') {
      part += list.slice(i, i + 2);
      i += 1;
    } else if (quote) {
      part += char;
      if (char === quote) quote = null;
    } else if (char === '"' || char === "'") {
      quote = char;
      part += char;
    } else if (char === ',' && depth === 0) {
      parts.push(part);
      part = '';
    } else {
      if (char === '(' || char === '[') depth += 1;
      if (char === ')' || char === ']') depth = Math.max(0, depth - 1);
      part += depth === 0 && '>+~'.includes(char) ? ` ${char} ` : char;
    }
  }
  parts.push(part);
  return parts
    .map((p) => p.replace(/\s+/g, ' ').trim())
    .sort()
    .join(', ');
}

export function duplicates(css) {
  const text = blanked(css);
  const found = [];
  // Each open block: its kind and, for a scope, the selectors seen in it.
  const stack = [{ kind: 'scope', seen: new Map() }];
  let start = 0;
  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    if (char === ';' || char === '}') {
      if (char === '}') {
        stack.pop();
        if (stack.length === 0) throw new Error(`unbalanced } at line ${lineOf(text, i)}`);
      }
      start = i + 1;
    } else if (char === '{') {
      const head = text.slice(start, i).replace(/\s+/g, ' ').trim();
      const parent = stack[stack.length - 1];
      if (head.startsWith('@')) {
        const keyframes = /^@(-\w+-)?keyframes\b/i.test(head);
        stack.push(keyframes ? { kind: 'keyframes' } : { kind: 'scope', seen: new Map() });
      } else {
        if (parent.kind === 'scope') {
          const line = lineOf(text, start + (text.slice(start, i).search(/\S/) || 0));
          const key = selectorKey(head);
          const first = parent.seen.get(key);
          if (first === undefined) parent.seen.set(key, line);
          else found.push({ selector: head, line, first });
        }
        stack.push({ kind: 'rule' });
      }
      start = i + 1;
    }
  }
  if (stack.length !== 1) throw new Error('a block is never closed');
  return found;
}

function lineOf(text, index) {
  let line = 1;
  for (let i = 0; i < index; i += 1) if (text[i] === '\n') line += 1;
  return line;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  let found;
  try {
    found = duplicates(readFileSync(path, 'utf8'));
  } catch (error) {
    console.log(`FAIL: css duplicates could not read ${path}: ${error.message}`);
    process.exit(1);
  }
  for (const { selector, line, first } of found) {
    console.log(`FAIL: duplicate selector "${selector}" at line ${line}, first used at line ${first}`);
  }
  if (found.length > 0) process.exit(1);
  console.log('css duplicates: no selector is written twice in one scope');
}
