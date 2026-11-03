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
  ['a list spaced differently', '.a,.b {}\n.a, .b {}', ['.a, .b']],
  ['a list in another order', '.a, .b {}\n.b, .a {}', ['.b, .a']],
  ['a combinator spaced differently', '.a>.b {}\n.a > .b {}', ['.a > .b']],
  ['a comma inside :is() is not the list', ':is(.a, .b) {}\n.a, .b {}', []],
  ['a combinator inside an attribute value', '[data-x="a>b"] {}\n[data-x="a > b"] {}', []],
  [
    'commas inside :is() keep two different lists apart',
    ':is(.x, .y) .p, :is(.z, .w) .q {}\n:is(.x, .w) .q, :is(.z, .y) .p {}',
    [],
  ],
  ['a list after a closed :is() is still split', ':is(.a) .b, .c {}\n.c, :is(.a) .b {}', ['.c, :is(.a) .b']],
  // Inside brackets a ~ is an operator, not a combinator, and is left as written (see the header).
  ['an attribute operator is not spaced as a combinator', '[x~=y] {}\n[x ~=y] {}', []],
  ['a bracket in a quoted value', '[x="["] .a, .b {}\n.b, [x="["] .a {}', ['.b, [x="["] .a']],
  ['a parenthesis in a quoted value', '[x="("], .c {}\n.c, [x="("] {}', ['.c, [x="("]']],
  ['a bracket in a single-quoted value', "[x='['] .a, .b {}\n.b, [x='['] .a {}", [".b, [x='['] .a"]],
  ['a quote of the other kind in a value', '[x="\'["] .a, .b {}\n.b, [x="\'["] .a {}', ['.b, [x="\'["] .a']],
  ['an escaped quote does not start a string', '.a\\"b, .c {}\n.c, .a\\"b {}', ['.c, .a\\"b']],
  ['an escaped comma is not the list', '.a\\,b {}\nb, .a\\ {}', []],
  ['an escaped combinator is not spaced', '.a\\>b {}\n.a\\ > b {}', []],
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
