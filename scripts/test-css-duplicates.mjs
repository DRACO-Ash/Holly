#!/usr/bin/env node
// test-css-duplicates.mjs :: the duplicate-selector check behaves on each case. Run by verify.sh.
import { duplicates } from './css-duplicates.mjs';

const cases = [
  ['a selector twice at the top level', '.a { color: red; }\n.b {}\n.a { margin: 0; }', ['.a']],
  ['its whitespace collapsed before comparing', '.a  .b {}\n.a .b {}', ['.a .b']],
  ['the same selector in two media blocks', '@media (x) { .a {} }\n@media (y) { .a {} }', []],
  ['twice in one media block', '@media (x) { .a {} .a {} }', ['.a']],
  ['once at the top and once in a media block', '.a {}\n@media (x) { .a {} }', []],
  ['keyframe steps are not selectors', '@keyframes k { 0% {} 50% {} 0% {} }', []],
  ['a brace in a comment or a string', '/* .a { */ .a { content: "}"; }\n.b {}', []],
  ['different selector lists', '.a, .b {}\n.a {}', []],
];
let failed = 0;
for (const [name, css, expected] of cases) {
  const got = duplicates(css).map((d) => d.selector);
  const ok = JSON.stringify(got) === JSON.stringify(expected);
  if (!ok) failed += 1;
  console.log(`${ok ? 'ok' : 'FAIL'}: ${name}${ok ? '' : ` (got ${JSON.stringify(got)})`}`);
}
for (const [name, css] of [
  ['an unbalanced close', '.a {} }'],
  ['a block never closed', '.a {'],
]) {
  let threw = false;
  try {
    duplicates(css);
  } catch {
    threw = true;
  }
  if (!threw) failed += 1;
  console.log(`${threw ? 'ok' : 'FAIL'}: ${name} is refused`);
}
if (failed > 0) {
  console.log(`css duplicates self-test: ${failed} cases misbehaved`);
  process.exit(1);
}
console.log('css duplicates self-test: all cases behaved');
