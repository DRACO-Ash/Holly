#!/usr/bin/env node
// test-contrast-check.mjs :: the contrast check's own self-test, run by verify.sh after it.
// Usage: node scripts/test-contrast-check.mjs [--case <what>]
//
// Each case edits a copy of the dashboard's stylesheet and runs scripts/contrast-check.mjs on
// it, the way the loop does. A form the check must refuse has to fail it with the reason the case
// quotes, so no case can pass on some other refusal, and a legitimate form has to pass. The first
// case is the stylesheet as it stands, which must measure exactly the pairs it measures today, so
// a change that narrows what the check measures fails it, as does a change to the sheet that adds
// or removes a pair until the count here is updated. A case's CSS is a rule of its own appended
// to the sheet, a value swapped in place, or a declaration or step added where nothing later
// overrides it, so what the check measures is what a browser would paint; a case declares a
// property twice only where that is what it tests. Each entry of each list the check measures,
// and each property it holds to the tokens, has a case of its own, from tables written out here
// and not read from the check, so the cases cannot move with its code; and where a refusal stops,
// a legitimate form just past it has a case too. Each view runs the check's --show on a copy and
// looks for text that must, or must not, reach its rules. An edit whose anchor is missing, or
// found twice, fails its case, so moving a rule cannot quietly retire one. The boundary cases hold
// each floor from both sides with colours measured beforehand: #777777 on white is 4.48:1 and
// #767676 is 4.54:1; #585858 on black is 2.95:1 and #5a5a5a is 3.04:1; in OKLab #06f365 is 0.197
// from the status green, #27ae60, and #05f665 is 0.205; and white text on black, both faded to
// half over a white frame, is 3.98:1, where over a black frame it would be 5.28:1.
// scripts/mutation-battery.mjs removes or moves each of the check's controls in turn and names
// the case here that goes red; --case runs that case alone.
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const checker = fileURLToPath(new URL('./contrast-check.mjs', import.meta.url));
const sheet = fileURLToPath(new URL('../frontend/src/styles/tokens.css', import.meta.url));
const source = readFileSync(sheet, 'utf8');

// Edits: each finds what it changes exactly once, or fails its case.
function once(css, anchor) {
  const count = css.split(anchor).length - 1;
  if (count !== 1) {
    throw new Error(`its anchor ${JSON.stringify(anchor.slice(0, 40))} is found ${count} times`);
  }
}
const swap = (anchor, text) => (css) => {
  once(css, anchor);
  return css.replace(anchor, () => text);
};
const add = (anchor, text) => swap(anchor, anchor + text);
const append = (text) => (css) => `${css}\n${text}`;
// A :root token's value, whatever it is today.
const token = (name, value) => (css) => {
  const lines = css.match(new RegExp(`\\n  ${name}: [^;]*;`, 'g')) ?? [];
  if (lines.length !== 1) throw new Error(`token ${name} is set ${lines.length} times, not once`);
  return css.replace(lines[0], () => `\n  ${name}: ${value};`);
};
// Declarations of the case's own, at the top of the first :root block.
const define = (text) => (css) => {
  if (!css.startsWith(':root {\n')) throw new Error('the stylesheet does not open with :root');
  return `:root {\n${text}${css.slice(':root {\n'.length)}`;
};
// The first :root block and the rules given, and nothing else.
const only = (text) => (css) => `${css.match(/^:root \{[^}]*\}/)[0]}\n\n${text}`;

// Anchors in the sheet: a field's edge, the flicker's keyframes, and the name its rule gives.
const FIELD = '  border: 1px solid var(--color-field-border);\n';
const FLICKER = '@keyframes crt-flicker {\n';
const NAMED = 'animation: crt-flicker ';

// Pieces of CSS: a rule, the case's own rule of declarations or of a body written out, a tint,
// a @keyframes block of one step, a deep animation, a step of the flicker's own, every surface
// black for an edge measured against a known colour, and a flicker for the sheets built from
// :root alone.
const rule = (selector, ...declarations) =>
  `${selector} {\n${declarations.map((d) => `  ${d};\n`).join('')}}\n`;
const own = (...declarations) => [append(rule('.case', ...declarations))];
const block = (body) => [append(`.case {\n${body}}\n`)];
const mix = (name, percent, rest = 'transparent') =>
  `color-mix(in srgb, var(${name}) ${percent}%, ${rest})`;
const keyframes = (name, declaration, at = '0%') =>
  `@keyframes ${name} {\n  ${at} {\n    ${declaration};\n  }\n}\n`;
const deep = (name, opacity = '0.2') => keyframes(name, `opacity: ${opacity}`);
const step = (declaration) => add(FLICKER, `  75% {\n    ${declaration};\n  }\n`);
const black = [
  '--color-bg',
  '--color-surface',
  '--color-surface-elevated',
  '--color-surface-hover',
  '--color-chrome',
  '--color-chrome-top',
  '--color-chrome-bottom',
].map((surface) => token(surface, '#000000'));
const FLICKER_ONLY =
  rule('[data-flicker="on"] .crt-screen', 'animation: crt-flicker 0.15s infinite') +
  `\n${deep('crt-flicker', '1')}\n`;
// A pulse at full strength in --case-tint, under the at-rule given.
const GLARE = keyframes('case-glare', `background: ${mix('--case-tint', 100)}`, '50%');
const glare = (tint, at = '@keyframes') => [
  define(`  --case-tint: ${tint};\n`),
  append(GLARE.replace('@keyframes', at)),
];

// Reasons the check gives more than once. A reason that opens with two spaces must start a line
// of the check's list, as each failure does, so a reason cannot be found inside another; CASE
// opens each failure of the case's own rule.
const CASE = '  .case: ';
const LITERAL_TEXT = `${CASE}color holds #333333`;
const NAMES_TWO = 'contrast: could not measure: the [data-flicker="on"] rules name 2 animations';
const TWO_BLOCKS = 'contrast: could not measure: @keyframes crt-flicker is defined 2 times';
const ESCAPED = 'a backslash, which CSS reads as an escape';
const UNCLOSED = 'a string its line or the sheet ends before it closes';
const URL_CALL = 'url(, whose unquoted form CSS reads as one token';
const EASING = 'cubic-bezier( or linear(, an easing that can carry an animation or a transition';
const FOREIGN = 'a character other than printable ASCII outside a string or a comment';
const BRACKETED = 'a brace or semicolon inside brackets, which CSS reads as part of them';
const IMAGE = 'linear-gradient(var(--color-text), var(--color-text))';
const ON_BG = ['color: var(--color-text)', 'background: var(--color-bg)'];
const FRAMED = `${CASE}paints --color-text text with a border image`;
const UNDER = '), which can paint under it and which no check measures';
const CLIPPED = 'can paint the text with the background, which no check measures';
const NOT_A_NAME = 'which is not a keyword, a time, a count or a name';
const FILL = "a fill the element's children inherit over their own colour";
const INHERITED = `${CASE}pairs inherited text with`;
const BESIDE = 'holds declarations beside blocks, which the rules here do not read';
const GLARED = '  @keyframes: --case-tint on 100% --case-tint over --color-bg: 1.00:1, below 4.5:1';

// The lists the check measures and the properties it holds to the tokens, written out here.
const TEXT_TOKENS = [
  '--color-text',
  '--color-text-muted',
  '--color-text-faint',
  '--color-accent',
  '--color-accent-strong',
  '--color-urgency-high',
  '--color-urgency-medium',
  '--color-urgency-low',
  '--color-error',
  '--color-success',
];
const SCREEN_SURFACES = [
  '--color-bg',
  '--color-surface',
  '--color-surface-elevated',
  '--color-surface-hover',
];
const CHROME_SURFACES = ['--color-chrome', '--color-chrome-top', '--color-chrome-bottom'];
const EDGE_TOKENS = ['--color-field-border'];
const STATUS_COLOURS = [
  '--color-success',
  '--color-urgency-low',
  '--color-urgency-medium',
  '--color-error',
  '--color-urgency-high',
];
const READOUT_TOKENS = [
  '--color-text',
  '--color-urgency-high',
  '--color-urgency-medium',
  '--color-urgency-low',
];
const READOUT_SURFACES = ['--color-bg', '--color-surface'];
// Each part of a selector the check takes for a rule on the chrome, and a selector holding it.
const CHROME_SELECTORS = [
  ['.app-header', '.app-header'],
  ['.app-nav', '.app-nav'],
  ['.nav-link', '.nav-link'],
  ['.brand-', '.brand-case'],
  ['.display-toggle', '.display-toggle'],
  ['.logout-btn', '.logout-btn'],
  ['.login-', '.login-case'],
  ['.form-error', '.form-error'],
];
const PULSE_TEXT = ['--color-text', '--color-text-muted'];
// Each property form the check holds to the tokens, as it names it, and a literal colour in it,
// with a vendor prefix where browsers know the property only with one; a font palette's colours
// in their own at-rule.
const PAINTING = [
  ['color', 'color: #ff0000'],
  ['background', 'background: #ff0000'],
  ['background-color', 'background-color: #ff0000'],
  ['background-image', 'background-image: linear-gradient(#ff0000, #ff0000)'],
  ['text-fill-color', '-webkit-text-fill-color: #ff0000'],
  ['text-stroke', '-webkit-text-stroke: 1px #ff0000'],
  ['text-stroke-color', '-webkit-text-stroke-color: #ff0000'],
  ['fill', 'fill: #ff0000'],
  ['stroke', 'stroke: #ff0000'],
  ['stop-color', 'stop-color: #ff0000'],
  ['flood-color', 'flood-color: #ff0000'],
  ['lighting-color', 'lighting-color: #ff0000'],
  ['caret', 'caret: #ff0000'],
  ['caret-color', 'caret-color: #ff0000'],
  ['accent-color', 'accent-color: #ff0000'],
  ['tap-highlight-color', '-webkit-tap-highlight-color: #ff0000'],
  ['text-decoration', 'text-decoration: underline #ff0000'],
  ['text-decoration-color', 'text-decoration-color: #ff0000'],
  ['text-emphasis', 'text-emphasis: filled #ff0000'],
  ['text-emphasis-color', 'text-emphasis-color: #ff0000'],
  ['scrollbar-color', 'scrollbar-color: #ff0000 #ff0000'],
  ['column-rule', 'column-rule: 1px solid #ff0000'],
  ['column-rule-color', 'column-rule-color: #ff0000'],
  ['outline', 'outline: 1px solid #ff0000'],
  ['outline-color', 'outline-color: #ff0000'],
  ['list-style', 'list-style: linear-gradient(#ff0000, #ff0000)'],
  ['list-style-image', 'list-style-image: linear-gradient(#ff0000, #ff0000)'],
  ['border-image', 'border-image: linear-gradient(#ff0000, #ff0000) 1'],
  ['border-image-source', 'border-image-source: linear-gradient(#ff0000, #ff0000)'],
  ['override-colors', 'override-colors: 0 #ff0000', '@font-palette-values --case'],
  ['border', 'border: 1px solid #ff0000'],
  ['border-color', 'border-color: #ff0000'],
  ['border-top', 'border-top: 1px solid #ff0000'],
  ['border-top-color', 'border-top-color: #ff0000'],
  ['border-right', 'border-right: 1px solid #ff0000'],
  ['border-right-color', 'border-right-color: #ff0000'],
  ['border-bottom', 'border-bottom: 1px solid #ff0000'],
  ['border-bottom-color', 'border-bottom-color: #ff0000'],
  ['border-left', 'border-left: 1px solid #ff0000'],
  ['border-left-color', 'border-left-color: #ff0000'],
  ['border-block', 'border-block: 1px solid #ff0000'],
  ['border-block-color', 'border-block-color: #ff0000'],
  ['border-block-start', 'border-block-start: 1px solid #ff0000'],
  ['border-block-start-color', 'border-block-start-color: #ff0000'],
  ['border-block-end', 'border-block-end: 1px solid #ff0000'],
  ['border-block-end-color', 'border-block-end-color: #ff0000'],
  ['border-inline', 'border-inline: 1px solid #ff0000'],
  ['border-inline-color', 'border-inline-color: #ff0000'],
  ['border-inline-start', 'border-inline-start: 1px solid #ff0000'],
  ['border-inline-start-color', 'border-inline-start-color: #ff0000'],
  ['border-inline-end', 'border-inline-end: 1px solid #ff0000'],
  ['border-inline-end-color', 'border-inline-end-color: #ff0000'],
  ['border-start', '-webkit-border-start: 1px solid #ff0000'],
  ['border-start-color', '-webkit-border-start-color: #ff0000'],
  ['border-end', '-webkit-border-end: 1px solid #ff0000'],
  ['border-end-color', '-webkit-border-end-color: #ff0000'],
  ['border-before', '-webkit-border-before: 1px solid #ff0000'],
  ['border-before-color', '-webkit-border-before-color: #ff0000'],
  ['border-after', '-webkit-border-after: 1px solid #ff0000'],
  ['border-after-color', '-webkit-border-after-color: #ff0000'],
];
const PREFIXES = ['-webkit-', '-moz-', '-ms-', '-o-', '-epub-'];
// Every word a painting value may hold, and every unit of a length, in rules that paint no text.
const EDGE = 'var(--color-field-border)';
const FADE = 'var(--color-bg), transparent';
const STOPS = 'var(--color-bg), var(--color-surface)';
const EVERY_WORD = [
  rule(
    '.case-sides',
    `border-top: thin solid ${EDGE}`,
    `border-right: medium dashed ${EDGE}`,
    `border-bottom: thick dotted ${EDGE}`,
    `border-left: 1px double ${EDGE}`,
    `border-block-start: 1px groove ${EDGE}`,
    `border-block-end: 1px ridge ${EDGE}`,
    `border-inline-start: 1px inset ${EDGE}`,
    `border-inline-end: 1px outset ${EDGE}`,
    `column-rule: 1px hidden ${EDGE}`,
    'outline: 1px solid currentColor',
  ),
  rule(
    '.case-units',
    `border-top: 1ch solid ${EDGE}`,
    `border-right: 1ex solid ${EDGE}`,
    `border-bottom: 1vh solid ${EDGE}`,
    `border-left: 1vw solid ${EDGE}`,
    `border-block-start: 1vmin solid ${EDGE}`,
    `border-block-end: 1vmax solid ${EDGE}`,
    `border-inline-start: 1.25PX solid ${EDGE}`,
    `border-inline-end: 0.5rem solid ${EDGE}`,
    `column-rule: 1em solid ${EDGE}`,
  ),
  rule('.case-lines', 'text-decoration: underline overline line-through wavy var(--color-accent)'),
  rule('.case-dot', 'text-emphasis: filled dot var(--color-accent)'),
  rule('.case-circle', 'text-emphasis: open double-circle var(--color-accent)'),
  rule('.case-triangle', 'text-emphasis: triangle var(--color-accent)'),
  rule('.case-sesame', 'text-emphasis: sesame var(--color-accent)'),
  rule(
    '.case-a',
    `background: linear-gradient(to right, ${STOPS}) -1px 0 no-repeat fixed padding-box`,
  ),
  rule(
    '.case-b',
    `background: radial-gradient(circle closest-side at center, ${FADE}) repeat scroll border-box`,
  ),
  rule(
    '.case-c',
    `background: radial-gradient(ellipse farthest-corner at left top, ${FADE}) repeat-x local ` +
      'content-box',
  ),
  rule('.case-d', `background: radial-gradient(closest-corner at right bottom, ${FADE}) repeat-y`),
  rule('.case-e', `background: radial-gradient(farthest-side, ${FADE}) center / cover`),
  rule('.case-f', `background: conic-gradient(from 0.5turn at 50% 50%, ${STOPS}) center / contain`),
  rule('.case-g', `background: repeating-linear-gradient(to bottom, ${STOPS} 1rem)`),
  rule('.case-h', `background: repeating-radial-gradient(${STOPS} 1em)`),
  rule('.case-i', `background: repeating-conic-gradient(from 1rad, ${STOPS} 10deg)`),
  rule('.case-j', `border-image: linear-gradient(${STOPS}) 1 fill / 1px / 0 stretch`),
  rule('.case-k', `border-image: linear-gradient(${STOPS}) 1 round space`),
  rule('.case-m', 'background: color-mix(in srgb, var(--color-accent) 8%, transparent)'),
  rule('.case-l', 'fill: none', 'stroke: inherit'),
].join('');
// Every keyword, and each form of a time, a flicker rule's animation may hold, its name repeated.
const EVERY_TIMING =
  'animation: crt-flicker 0.15s infinite linear normal forwards running, ' +
  'crt-flicker 1S ease reverse backwards paused, crt-flicker 150MS ease-in alternate both, ' +
  'crt-flicker +.5s ease-out alternate-reverse none, crt-flicker 10.5s ease-in-out, ' +
  'crt-flicker 1s step-start, crt-flicker 1s step-end, crt-flicker 1s INFINITE, ' +
  'crt-flicker 1s STEPS(4, END), crt-flicker 1s steps(2);';

// [what, the reason the check must give, null where it must pass, or { passes: text } where it
// must pass and print text, edits, or null to run the check with no path].
const cases = [
  ['the stylesheet as it stands', { passes: 'contrast: all 220 pairs clear the floor' }, []],

  // A colour of a rule's own, in each property that paints one, with each vendor prefix.
  ...PAINTING.map(([form, declaration, selector = '.case']) => [
    `painting property ${form}`,
    `  ${selector}: ${declaration.slice(0, declaration.indexOf(':'))} holds #ff0000, which no ` +
      'check measures',
    [append(rule(selector, declaration))],
  ]),
  ...PREFIXES.map((prefix) => [
    `vendor prefix ${prefix}`,
    `${CASE}${prefix}border-image holds #ff0000`,
    own(`${prefix}border-image: linear-gradient(#ff0000, #ff0000) 1`),
  ]),
  ['an rgba background', `${CASE}background holds rgba`, own('background: rgba(1, 2, 3, 0.9)')],
  ['a property name in capitals', LITERAL_TEXT, own('COLOR: #333333')],
  ['a literal colour with a space before its colon', LITERAL_TEXT, own('color : #333333')],
  [
    'a literal border colour with no space after its colon',
    `${CASE}border-color holds #333333`,
    own('border-color:#333333'),
  ],
  ['a named colour', `${CASE}color holds crimson`, own('color: crimson')],
  [
    'a named colour, its whole reason',
    `${CASE}color holds crimson, which no check measures (accepted: var(--token), a tint ` +
      'color-mix(in srgb, var(--token) N%, transparent), a gradient of those, a length, ' +
      'transparent, none, currentColor or inherit, with or without !important)',
    own('color: crimson'),
  ],
  [
    '!important inside a value',
    `${CASE}border holds !important,`,
    own('border: 1px !important solid var(--color-field-border)'),
  ],
  [
    'a colour with a keyword after its token',
    `${CASE}color is var(--color-text) inherit, a text colour no check measures`,
    own('color: var(--color-text) inherit'),
  ],
  [
    'a colour with a token after its keyword',
    `${CASE}color is inherit var(--color-text), a text colour no check measures`,
    own('color: inherit var(--color-text)'),
  ],
  [
    'a literal colour in a rule whose selectors span lines',
    '  .case, .case-two: color holds #333333',
    [append('.case,\n  .case-two {\n  color: #333333;\n}\n')],
  ],
  [
    'a background written over lines is named on one',
    `${CASE}pairs --color-text-faint with linear-gradient( var(--color-accent), ` +
      'var(--color-accent) ), a background no check measures',
    own(
      'color: var(--color-text-faint)',
      'background: linear-gradient(\n    var(--color-accent),\n    var(--color-accent)\n  )',
    ),
  ],
  [
    'crimson in a gradient',
    `${CASE}background holds crimson`,
    own('background: linear-gradient(crimson, crimson)'),
  ],
  [
    'gold in a gradient',
    `${CASE}background holds gold`,
    own('background: linear-gradient(gold, gold)'),
  ],
  [
    'ivory in a gradient',
    `${CASE}background holds ivory`,
    own('background: linear-gradient(ivory, ivory)'),
  ],
  [
    'a system colour in a gradient',
    `${CASE}background holds Canvas`,
    own('background: linear-gradient(Canvas, Canvas)'),
  ],
  [
    'a system colour under forced colours, which nothing measures',
    `${CASE}color holds CanvasText`,
    [append(`@media (forced-colors: active) {\n${rule('.case', 'color: CanvasText')}}\n`)],
  ],
  ['a colour in oklab()', `${CASE}background holds oklab`, own('background: oklab(1 0 0)')],
  [
    'a mix in another colour space',
    `${CASE}background holds color-mix,`,
    own('background: color-mix(in oklab, var(--color-bg) 50%, transparent)'),
  ],
  [
    'a border in a mix of two tokens',
    `${CASE}border-color holds color-mix,`,
    own(`border-color: ${mix('--color-accent', 50, 'var(--color-error)')}`),
  ],
  [
    'a length glued to a literal colour',
    `${CASE}border holds 1px#333333,`,
    own('border: 1px#333333 solid'),
  ],
  ['color: initial', `${CASE}color holds initial,`, own('color: initial')],
  ['color: unset', `${CASE}color holds unset,`, own('color: unset')],
  ['color: revert', `${CASE}color holds revert,`, own('color: revert')],
  [
    'an accent colour left to the browser',
    `${CASE}accent-color holds auto,`,
    own('accent-color: auto'),
  ],
  [
    "text on the browser's own background",
    `${CASE}background holds revert,`,
    own('color: var(--color-text)', 'background: revert'),
  ],
  [
    'a field edge as a literal border',
    'select, textarea: border holds #1a1a1a',
    [swap(FIELD, '  border: 1px solid #1a1a1a;\n')],
  ],

  // Tokens: defined only in the first :root, once, and named only when they exist.
  [
    'a token redefined in a rule',
    `${CASE}defines --color-text outside the first :root block`,
    own('--color-text: #333333'),
  ],
  [
    'a custom property local to a rule',
    `${CASE}defines --local-ink outside the first :root block`,
    own('--local-ink: #333333', 'border-color: var(--local-ink)'),
  ],
  [
    'a second :root block in a media query',
    '  :root: defines --color-text outside the first :root block',
    [append(`@media (min-width: 1px) {\n${rule(':root', '--color-text: #333333')}}\n`)],
  ],
  [
    ':root .x with a literal colour',
    '  :root .case: color holds #333333',
    [append(rule(':root .case', 'color: #333333'))],
  ],
  ['a literal colour in :root', '  :root: color holds #333333', [define('  color: #333333;\n')]],
  [
    'a token defined twice in :root',
    '  :root: declares --color-text twice',
    [define('  --color-text: #000000;\n')],
  ],
  [
    'a var() naming no token, in a pair',
    'contrast: could not measure: --no-such-token is not a token in :root',
    own('color: var(--no-such-token)', 'background: var(--color-bg)'),
  ],
  [
    'a var() naming no token, in a rule without a pair',
    `${CASE}border-color names --no-such-token, which is not a :root token`,
    own('border-color: var(--no-such-token)'),
  ],
  ['a token whose fallback is a literal', LITERAL_TEXT, own('color: var(--color-text, #333333)')],
  [
    'a token whose fallback is a function holding a var()',
    `${CASE}border-color holds var,`,
    own('border-color: var(--color-accent, linear-gradient(var(--color-bg), transparent))'),
  ],

  // Text: painted in a token, on a background where the pair is measured, as CSS paints it.
  [
    'a text colour that is a tint of a token',
    `${CASE}color is ${mix('--color-text-faint', 30)}, a text colour no check measures`,
    own(`color: ${mix('--color-text-faint', 30)}`),
  ],
  [
    'transparent text',
    `${CASE}color is transparent, a text colour no check measures`,
    own('color: transparent'),
  ],
  [
    'text on a gradient of tokens',
    `${CASE}pairs --color-text-faint with linear-gradient(var(--color-accent), ` +
      'var(--color-accent)), a background no check measures',
    own(
      'color: var(--color-text-faint)',
      'background: linear-gradient(var(--color-accent), var(--color-accent))',
    ),
  ],
  [
    'text on a mix of two tokens',
    `${CASE}background holds color-mix,`,
    own(
      'color: var(--color-text-faint)',
      `background: ${mix('--color-accent', 90, 'var(--color-text)')}`,
    ),
  ],
  [
    'a tint above 100%',
    `${CASE}background holds color-mix,`,
    own('color: var(--color-bg)', `background: ${mix('--color-text', 150)}`),
  ],
  [
    'a surface token as text with no background of its own',
    `${CASE}colours text with --color-bg, which is not a text token, and sets no background ` +
      'to measure it on',
    own('color: var(--color-bg)'),
  ],
  [
    'a text fill the colour of its background',
    `${CASE}-webkit-text-fill-color is var(--color-bg), ${FILL}`,
    own(
      'color: var(--color-text)',
      '-webkit-text-fill-color: var(--color-bg)',
      'background: var(--color-bg)',
    ),
  ],
  [
    'a text fill that is a tint of a token',
    `${CASE}-webkit-text-fill-color is ${mix('--color-bg', 100)}, ${FILL}`,
    own(`-webkit-text-fill-color: ${mix('--color-bg', 100)}`, 'background: var(--color-bg)'),
  ],
  [
    "text in the parent's colour over a background of its own",
    `${INHERITED} var(--color-accent), a background no check measures`,
    own('color: inherit', 'background: var(--color-accent)'),
  ],
  [
    "text in the parent's colour marked !important over a background of its own",
    `${INHERITED} var(--color-accent), a background no check measures`,
    own('color: inherit !important', 'background: var(--color-accent)'),
  ],
  [
    'text in currentColor over a tint of its own',
    `${INHERITED} ${mix('--color-accent', 30)}, a background no check measures`,
    own('color: currentColor', `background: ${mix('--color-accent', 30)}`),
  ],
  [
    'a fill by keyword over a background-color of its own',
    `${INHERITED} var(--color-surface), a background no check measures`,
    own('-webkit-text-fill-color: inherit', 'background-color: var(--color-surface)'),
  ],
  [
    "text in the parent's colour over a background image",
    `${CASE}paints inherited text over a background image, which no check measures`,
    own('color: inherit', `background-image: ${IMAGE}`),
  ],
  [
    "text in the parent's colour with a border image",
    `${CASE}paints inherited text with a border image (border-image ${IMAGE} 1${UNDER}`,
    own('color: inherit', `border-image: ${IMAGE} 1`),
  ],
  [
    'every colour reset at once',
    `${CASE}all initial sets every colour the rule paints to a value no check measures`,
    own('ALL: initial'),
  ],
  [
    'a background clipped to the text',
    `${CASE}-webkit-background-clip text ${CLIPPED}`,
    own('-webkit-background-clip: text'),
  ],
  [
    'a background clipped to the text among other boxes',
    `${CASE}-webkit-background-clip padding-box, text ${CLIPPED}`,
    own('-webkit-background-clip: padding-box, text'),
  ],
  [
    'a background clipped to the text in capitals',
    `${CASE}-webkit-background-clip TEXT ${CLIPPED}`,
    own('-webkit-background-clip: TEXT'),
  ],
  [
    'a background clipped through a token',
    `${CASE}background-clip var(--case-clip) ${CLIPPED}`,
    [define('  --case-clip: padding-box;\n'), ...own('background-clip: var(--case-clip)')],
  ],
  [
    'text on itself',
    `${CASE}--color-text on --color-text: 1.00:1, below 4.5:1`,
    own('color: var(--color-text)', 'background: var(--color-text)'),
  ],
  [
    'text on its own background-color',
    `${CASE}--color-text on --color-text: 1.00:1, below 4.5:1`,
    own('color: var(--color-text)', 'background-color: var(--color-text)'),
  ],
  [
    'text marked !important in the colour of its background',
    `${CASE}--color-bg on --color-bg: 1.00:1, below 4.5:1`,
    own('color: var(--color-bg) !important', 'background: var(--color-bg)'),
  ],
  [
    'text on a tint of itself',
    `${CASE}--color-text on 100% --color-text over --color-bg: 1.00:1, below 4.5:1`,
    own('color: var(--color-text)', `background: ${mix('--color-text', 100)}`),
  ],
  [
    'a text colour declared twice',
    `${CASE}declares color twice`,
    own('color: var(--color-text)', 'background: var(--color-bg)', 'color: var(--color-bg)'),
  ],
  [
    'a text fill declared twice',
    `${CASE}declares -webkit-text-fill-color twice`,
    own(
      '-webkit-text-fill-color: var(--color-bg) !important',
      'background: var(--color-bg)',
      '-webkit-text-fill-color: var(--color-text)',
    ),
  ],
  [
    'text on a token that a background shorthand follows with none',
    `${CASE}pairs --color-text with var(--color-text) none, a background no check measures`,
    own('color: var(--color-text)', 'background: var(--color-text) none'),
  ],
  [
    'text on a token that a background shorthand leads with none',
    `${CASE}pairs --color-text with none var(--color-text), a background no check measures`,
    own('color: var(--color-text)', 'background: none var(--color-text)'),
  ],
  [
    'a failing sheet says how many of its pairs fail',
    'contrast: 1 of 221 pairs fail:',
    own('color: var(--color-text)', 'background: var(--color-text)'),
  ],
  [
    'text over a background image is not measured as well',
    'contrast: 1 of 220 pairs fail:',
    own(...ON_BG, `background-image: ${IMAGE}`),
  ],
  [
    'text with a border image is not measured as well',
    'contrast: 1 of 220 pairs fail:',
    own(...ON_BG, `border-image: ${IMAGE} 1`),
  ],
  [
    'background and background-color in one rule',
    `${CASE}sets both background and background-color`,
    own(
      'color: var(--color-text)',
      'background: var(--color-bg)',
      'background-color: var(--color-text)',
    ),
  ],
  [
    'text over a background image',
    `${CASE}paints --color-text text over a background image, which no check measures`,
    own(
      'color: var(--color-text)',
      'background: var(--color-bg)',
      'background-image: linear-gradient(var(--color-text), var(--color-text))',
    ),
  ],
  [
    'text over a background image, with no background colour',
    `${CASE}paints --color-text text over a background image, which no check measures`,
    own('color: var(--color-text)', `background-image: ${IMAGE}`),
  ],
  [
    'text over a border image whose middle is filled',
    `${FRAMED} (border-image ${IMAGE} fill 1${UNDER}`,
    own(...ON_BG, `border-image: ${IMAGE} fill 1`),
  ],
  [
    'text over a border image filled by its slice',
    `${FRAMED} (border-image-source ${IMAGE}${UNDER}`,
    own(...ON_BG, `border-image-source: ${IMAGE}`, 'border-image-slice: 1 fill'),
  ],
  [
    'text over a prefixed border image whose middle is filled',
    `${FRAMED} (-webkit-border-image ${IMAGE} fill 1${UNDER}`,
    own(...ON_BG, `-webkit-border-image: ${IMAGE} fill 1`),
  ],
  [
    'text over a border image filled in capitals',
    `${FRAMED} (border-image ${IMAGE} FILL 1${UNDER}`,
    own(...ON_BG, `border-image: ${IMAGE} FILL 1`),
  ],
  [
    'text over a border image filled right before its width',
    `${FRAMED} (border-image ${IMAGE} 1 fill/1px${UNDER}`,
    own(...ON_BG, `border-image: ${IMAGE} 1 fill/1px`),
  ],
  [
    'text over a border image filled right after its image',
    `${FRAMED} (border-image ${IMAGE}fill 1${UNDER}`,
    own(...ON_BG, `border-image: ${IMAGE}fill 1`),
  ],
  [
    'text with a border image whose middle is empty',
    `${FRAMED} (border-image ${IMAGE} 1${UNDER}`,
    own(...ON_BG, `border-image: ${IMAGE} 1`),
  ],
  [
    'text with a prefixed border image, which WebKit fills without the word',
    `${FRAMED} (-webkit-border-image ${IMAGE} 1${UNDER}`,
    own(...ON_BG, `-webkit-border-image: ${IMAGE} 1`),
  ],
  [
    'text with a border image through a token',
    `${FRAMED} (border-image var(--case-image) 1${UNDER}`,
    [define(`  --case-image: ${IMAGE};\n`), ...own(...ON_BG, 'border-image: var(--case-image) 1')],
  ],
  [
    'text with a border image slice whose fallback fills',
    `${FRAMED} (border-image-slice var(--case-none, fill 1)${UNDER}`,
    own(...ON_BG, 'border-image-slice: var(--case-none, fill 1)'),
  ],
  [
    'text with a border image width alone',
    `${FRAMED} (border-image-width 2px${UNDER}`,
    own(...ON_BG, 'border-image-width: 2px'),
  ],

  // Each entry of each list the check measures.
  ...TEXT_TOKENS.map((t) => [
    `text token ${t}`,
    `  ${t} on --color-chrome-top: 1.00:1, below 4.5:1`,
    [token(t, 'var(--color-chrome-top)')],
  ]),
  ...SCREEN_SURFACES.map((s) => [
    `screen surface ${s}`,
    `  --color-text on ${s}: 1.00:1, below 4.5:1`,
    [token(s, 'var(--color-text)')],
  ]),
  ...CHROME_SURFACES.map((s) => [
    `chrome surface ${s}`,
    `  --color-text on ${s}: 1.00:1, below 4.5:1`,
    [token(s, 'var(--color-text)')],
  ]),
  ...EDGE_TOKENS.map((e) => [
    `edge token ${e}`,
    `  ${e} edge on --color-bg: 1.00:1, below 3:1`,
    [token(e, 'var(--color-bg)')],
  ]),
  ...STATUS_COLOURS.map((s) => [
    `status colour ${s}`,
    `  --color-accent is 0.000 from the status colour ${s} in OKLab, below 0.2`,
    [token('--color-accent', `var(${s})`)],
  ]),
  ...READOUT_TOKENS.map((r) => [
    `readout token ${r}`,
    `  ${r} readout on --color-bg, under the scanlines: 1.00:1, below 3:1`,
    [token(r, 'var(--color-bg)')],
  ]),
  ...READOUT_SURFACES.map((s) => [
    `readout surface ${s}`,
    `  --color-text readout on ${s}, under the scanlines: 1.00:1, below 3:1`,
    [token(s, 'var(--color-text)')],
  ]),
  ...CHROME_SELECTORS.map(([part, selector]) => [
    `chrome selector ${part}`,
    `  ${selector}: --color-chrome-top on 0% --color-bg over --color-chrome-top: 1.00:1, ` +
      'below 4.5:1',
    [
      append(
        rule(selector, 'color: var(--color-chrome-top)', `background: ${mix('--color-bg', 0)}`),
      ),
    ],
  ]),
  ...PULSE_TEXT.map((t) => [
    `pulse text ${t}`,
    `  @keyframes: ${t} on 100% --case-tint over --color-bg: 1.00:1, below 4.5:1`,
    glare(`var(${t})`),
  ]),
  ["pulse text in the tint's own colour", GLARED, glare('var(--color-accent)')],
  [
    'pulse text over a tint at half strength, on the page background',
    '  @keyframes: --case-tint on 50% --case-tint over --color-bg: 3.98:1, below 4.5:1',
    [
      define('  --case-tint: #ffffff;\n'),
      token('--color-bg', '#000000'),
      token('--color-surface', '#ffffff'),
      append(keyframes('case-glare', `background: ${mix('--case-tint', 50)}`, '50%')),
    ],
  ],
  ['a pulse under @-webkit-keyframes', GLARED, glare('var(--color-accent)', '@-webkit-keyframes')],
  ['a pulse under @KEYFRAMES', GLARED, glare('var(--color-accent)', '@KEYFRAMES')],
  [
    'a pulse under @keyframes with its quoted name right after it',
    GLARED,
    [
      define('  --case-tint: var(--color-accent);\n'),
      append(GLARE.replace('@keyframes case-glare', '@keyframes"case-glare"')),
    ],
  ],
  [
    'a pulse block closed right after its last step',
    GLARED,
    [define('  --case-tint: var(--color-accent);\n'), append(GLARE.replace('  }\n}\n', '  }}\n'))],
  ],
  [
    'a pulse mixed otherwise than as a tint',
    '  @keyframes case-glare: mixes a colour other than as a tint',
    [
      append(
        keyframes(
          'case-glare',
          'background: color-mix(in srgb, 100% var(--color-text), transparent)',
          '50%',
        ),
      ),
    ],
  ],
  [
    'a pulse mixed in capitals',
    '  @keyframes case-glare: mixes a colour other than as a tint',
    [
      append(
        keyframes(
          'case-glare',
          'background: COLOR-MIX(in srgb, var(--color-text) 90%, var(--color-bg))',
          '50%',
        ),
      ),
    ],
  ],

  // Each measured family, below its floor.
  [
    'a flicker to black',
    '  --color-text on --color-bg, flickering: 1.00:1, below 4.5:1',
    [step('opacity: 0')],
  ],
  [
    'the flicker fades the screen over the frame',
    '  --color-text on --color-bg, flickering: 3.98:1, below 4.5:1',
    [
      token('--color-text', '#ffffff'),
      token('--color-bg', '#000000'),
      token('--color-chrome-top', '#ffffff'),
      token('--color-chrome', '#000000'),
      step('opacity: 0.5'),
    ],
  ],
  [
    'the flicker fades the screen over the frame, by a percentage',
    '  --color-text on --color-bg, flickering: 3.98:1, below 4.5:1',
    [
      token('--color-text', '#ffffff'),
      token('--color-bg', '#000000'),
      token('--color-chrome-top', '#ffffff'),
      token('--color-chrome', '#000000'),
      step('opacity: 50%'),
    ],
  ],
  [
    'scanlines that black out the readouts',
    '  --color-text readout on --color-bg, under the scanlines: 1.00:1, below 3:1',
    [token('--scanline-alpha', '0.999')],
  ],

  // Each floor, held from both sides.
  [
    'text just under 4.5:1',
    `${CASE}--case-ink on --case-paper: 4.48:1, below 4.5:1`,
    [
      define('  --case-ink: #777777;\n  --case-paper: #ffffff;\n'),
      ...own('color: var(--case-ink)', 'background: var(--case-paper)'),
    ],
  ],
  [
    'text just over 4.5:1',
    null,
    [
      define('  --case-ink: #767676;\n  --case-paper: #ffffff;\n'),
      ...own('color: var(--case-ink)', 'background: var(--case-paper)'),
    ],
  ],
  [
    'a field edge just under 3:1',
    '  --color-field-border edge on --color-bg: 2.95:1, below 3:1',
    [...black, token('--color-field-border', '#585858')],
  ],
  ['a field edge just over 3:1', null, [...black, token('--color-field-border', '#5a5a5a')]],
  [
    'an accent just under 0.2 from a status colour',
    '  --color-accent is 0.197 from the status colour --color-success in OKLab, below 0.2',
    [token('--go', '#27ae60'), token('--color-accent', '#06f365')],
  ],
  [
    'an accent just over 0.2 from a status colour',
    null,
    [token('--go', '#27ae60'), token('--color-accent', '#05f665')],
  ],

  // What cannot be measured, or would be read otherwise than CSS reads it, fails closed.
  [
    'a stylesheet without :root',
    'contrast: no :root block in',
    [() => rule('.case', 'color: var(--color-text)')],
  ],
  [
    'a token that refers to itself',
    'contrast: could not measure: --color-text-faint refers to itself',
    [token('--color-text-faint', 'var(--color-text-faint)')],
  ],
  [
    'a token that is not an opaque colour',
    'contrast: could not measure: --color-text-faint is #8493a880, not an opaque #rrggbb colour',
    [token('--color-text-faint', '#8493a880')],
  ],
  [
    'a token whose value holds a var() after another word',
    'contrast: could not measure: --color-text-faint is x var(--color-text), not an opaque',
    [token('--color-text-faint', 'x var(--color-text)')],
  ],
  [
    'a token whose value holds a word after a var()',
    'contrast: could not measure: --color-text-faint is var(--color-text) x, not an opaque',
    [token('--color-text-faint', 'var(--color-text) x')],
  ],
  [
    'a token whose value holds a colour after another word',
    'contrast: could not measure: --color-text-faint is x #e2e8f0, not an opaque',
    [token('--color-text-faint', 'x #e2e8f0')],
  ],
  [
    'scanlines at a negative opacity',
    'contrast: could not measure: --scanline-alpha is -0.5, not an opacity',
    [token('--scanline-alpha', '-0.5')],
  ],
  [
    'scanlines at an opacity of 1',
    'contrast: could not measure: --scanline-alpha is 1, not an opacity',
    [token('--scanline-alpha', '1')],
  ],
  ['scanlines at an opacity of 0', null, [token('--scanline-alpha', '0')]],
  [
    'a sheet with no rule that pairs text with a background',
    'no rule pairs a text colour with a background: the parser has drifted',
    [
      only(
        FLICKER_ONLY +
          keyframes('case-pulse', `background: ${mix('--color-urgency-high', 25)}`, '50%'),
      ),
    ],
  ],
  [
    'a sheet whose only text rule sets no background',
    'no rule pairs a text colour with a background: the parser has drifted',
    [
      only(
        FLICKER_ONLY +
          keyframes('case-pulse', `background: ${mix('--color-urgency-high', 25)}`, '50%') +
          rule('.case', 'color: var(--color-text)'),
      ),
    ],
  ],
  [
    'a sheet with no animation tint',
    'no animation tint found: the parser has drifted',
    [only(FLICKER_ONLY + rule('.case', 'color: var(--color-text)', 'background: var(--color-bg)'))],
  ],
  [
    'a rule nested in another',
    `${CASE}nests .inner {...} in its block`,
    block('  color: #333333;\n  .inner {\n    color: var(--color-text);\n  }\n'),
  ],
  [
    'a rule nested in another inside @media',
    `${CASE}nests .inner {...} in its block`,
    [
      append(
        `@media (min-width: 1px) {\n${rule('.case', 'color: var(--color-text)').replace(
          '}',
          `${rule('.inner', 'color: var(--color-text)')}}`,
        )}}\n`,
      ),
    ],
  ],
  [
    'a sheet that opens with a brace holding a rule',
    '  : nests .case {...} in its block',
    [(css) => `{\n.case {\n  order: 1;\n}\n}\n${css}`],
  ],
  [
    'a rule nested in another is refused once',
    'contrast: 1 of 220 pairs fail:',
    block('  color: #333333;\n  .inner {\n    order: 1;\n  }\n'),
  ],
  [
    'two blocks never closed are named by the inner one',
    `${CASE}its block is never closed`,
    [append('@media (min-width: 1px) {\n.case {\n  color: var(--color-text);\n')],
  ],
  [
    'an @scope holding a declaration beside a rule',
    `  @scope (.case): ${BESIDE}`,
    [append('@scope (.case) {\n  color: #333333;\n  .inner {\n    order: 1;\n  }\n}\n')],
  ],
  [
    'an @page holding a declaration after a margin box',
    `  @page: ${BESIDE}`,
    [append('@page {\n  @top-left {\n    content: "x";\n  }\n  color: var(--color-text)\n}\n')],
  ],
  [
    'a block never closed',
    `${CASE}its block is never closed`,
    [append('.case {\n  color: #333333;\n')],
  ],
  [
    'an @import',
    '  @import "./case.css": brings in a stylesheet this check does not read',
    [(css) => `@import "./case.css";\n${css}`],
  ],
  [
    'an @IMPORT in capitals',
    '  @IMPORT "./case.css": brings in a stylesheet this check does not read',
    [(css) => `@IMPORT "./case.css";\n${css}`],
  ],
  [
    'an @import after a comment',
    '  @import url("./case.css"): brings in a stylesheet this check does not read',
    [(css) => `@import/**/url("./case.css");\n${css}`],
  ],
  [
    'an @import right after a @charset',
    '  @import "./case.css": brings in a stylesheet this check does not read',
    [(css) => `@charset "utf-8";@import "./case.css";\n${css}`],
  ],
  [
    'an @import written over three lines is named on one',
    '  @import "./case.css" screen: brings in a stylesheet this check does not read',
    [(css) => `@import\n  "./case.css"\n  screen;\n${css}`],
  ],
  [
    'an @property registering a token',
    '  @property --color-text: registers a custom property',
    [
      append(
        '@property --color-text {\n  syntax: "<color>";\n  inherits: false;\n' +
          '  initial-value: #000000;\n}\n',
      ),
    ],
  ],
  [
    'an @PROPERTY in capitals',
    '  @PROPERTY --case-ink: registers a custom property',
    [append('@PROPERTY --case-ink {\n  syntax: "*";\n  inherits: true;\n}\n')],
  ],
  [
    'a no-break space between a property and its value',
    FOREIGN,
    own('border:\u00a01px solid var(--color-field-border)'),
  ],
  [
    'a byte order mark inside the sheet',
    FOREIGN,
    own('border:\ufeff1px solid var(--color-field-border)'),
  ],
  [
    'a control character between a property and its value',
    FOREIGN,
    own('border:\u000b1px solid var(--color-field-border)'),
  ],
  [
    'a no-break space in a selector, reported on its line',
    `  line 2: ${FOREIGN}`,
    [(css) => `.case\n.case-two\u00a0.inner {\n  order: 1;\n}\n${css}`],
  ],
  [
    'an easing that can overshoot, in a transition',
    EASING,
    own('transition: color 1s cubic-bezier(0.5, -1, 0.5, 2)'),
  ],
  ['a linear() easing', EASING, own('animation-timing-function: linear(0, 1.5, 1)')],
  ['an easing in capitals', EASING, own('transition: color 1s CUBIC-BEZIER(0.5, -1, 0.5, 2)')],
  [
    'two backslashes on one line, reported once',
    `  line 2: ${ESCAPED}`,
    [(css) => `.case {\n  x\\a\\b: 1;\n}\n${css}`],
  ],
  [
    'backslashes on two lines, the second twice, each line reported once',
    `  line 2, 3: ${ESCAPED}`,
    [(css) => `.case {\n  a\\b: 1;\n  c\\d\\e: 1;\n}\n${css}`],
  ],
  [
    'a sheet that opens with url(, reported on its first line',
    `  line 1: ${URL_CALL}`,
    [(css) => `url(x) .case {\n}\n${css}`],
  ],
  [
    'two quotes that carriage returns end, reported on their lines',
    `  line 2, 4: ${UNCLOSED}`,
    [(css) => `.case {\r  content: "x\r  ;\r  content: "y\r  ;\r}\r${css}`],
  ],
  [
    'a colour scheme switched outside :root',
    `${CASE}color-scheme light outside the first :root block switches the browser's own colours`,
    own('color-scheme: light'),
  ],
  [
    'the flicker eased past its keyframes',
    EASING,
    [swap(NAMED, `${NAMED}cubic-bezier(0.1, 0.7, 1, 0.1) `)],
  ],
  ['the flicker eased by linear()', EASING, [swap(NAMED, `${NAMED}linear(0, 1.5, 1) `)]],
  [
    'a flicker eased by steps() through var()',
    `the [data-flicker="on"] rules hold steps(var(--case-steps), ${NOT_A_NAME}`,
    [swap(NAMED, `${NAMED}steps(var(--case-steps), end) `)],
  ],
  [
    "a flicker's steps() closed twice",
    `the [data-flicker="on"] rules hold ), ${NOT_A_NAME}`,
    [swap(NAMED, `${NAMED}steps(2, end)) `)],
  ],
  ['an escaped property name', ESCAPED, own('\\63 olor: #333333')],
  [
    'an escaped selector naming the flicker',
    ESCAPED,
    [
      append(
        rule('[data-fl\\69 cker="on"] .crt-content', 'animation: crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    'a closing brace inside brackets',
    BRACKETED,
    own('background: var(--color-surface)', 'grid-area: a(})', 'color: var(--color-bg)'),
  ],
  [
    'a closing brace inside square brackets',
    BRACKETED,
    own(
      'background: var(--color-surface)',
      'grid-template-columns: [a}] 1fr',
      'color: var(--color-bg)',
    ),
  ],
  ['an opening brace inside brackets', BRACKETED, own('grid-area: a({)')],
  ['a semicolon inside brackets', BRACKETED, own('grid-area: a(;)')],
  ['a bracket closed by the wrong closer', BRACKETED, own('grid-area: a(]')],
  [
    'a closing brace inside brackets after a url()',
    BRACKETED,
    own('background: var(--color-surface)', 'grid-area: a(url(x) })', 'color: var(--color-bg)'),
  ],
  [
    'a brace inside brackets on the third line is reported there',
    `  line 3: ${BRACKETED}`,
    [(css) => `\n.case {\n  grid-area: a(});\n}\n${css}`],
  ],
  [
    'a closing brace inside brackets in the flicker rule',
    BRACKETED,
    [
      append(
        rule(
          '[data-flicker="on"] .crt-content',
          'grid-area: a(})',
          'animation: crt-deep 0.1s infinite',
        ) + deep('crt-deep', '0.05'),
      ),
    ],
  ],
  [
    'an escaped property in the flicker rule',
    ESCAPED,
    [
      append(
        rule('[data-flicker="on"] .crt-content', 'anima\\tion: crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],

  // The flicker: one animation, defined once, that changes opacity only.
  ['a 50% flicker', '  --color-text-muted on --color-bg, flickering: ', [step('opacity: 0.5')]],
  [
    'a flicker opacity that is not a number',
    '@keyframes crt-flicker sets opacity calc(0.5), not a number from 0 to 1 or a percentage',
    [step('opacity: calc(0.5)')],
  ],
  [
    'a flicker opacity above 1',
    '@keyframes crt-flicker sets opacity 1.01, not a number from 0 to 1 or a percentage',
    [step('opacity: 1.01')],
  ],
  [
    'a flicker opacity below 0, as a percentage',
    '@keyframes crt-flicker sets opacity -96%, not a number from 0 to 1 or a percentage',
    [step('opacity: -96%')],
  ],
  [
    'a flicker that also dims by filter',
    '@keyframes crt-flicker sets filter; the flicker may change opacity only',
    [step('filter: brightness(0.3)')],
  ],
  [
    'a flicker that also dims by filter, spaced before its colon',
    '@keyframes crt-flicker sets filter; the flicker may change opacity only',
    [step('filter : brightness(0.3)')],
  ],
  [
    'a flicker opacity with a letter after its percentage',
    '@keyframes crt-flicker sets opacity 50%x, not a number from 0 to 1 or a percentage',
    [step('opacity: 50%x')],
  ],
  [
    'a flicker opacity holding a colon',
    '@keyframes crt-flicker sets opacity 0.5:1, not a number from 0 to 1 or a percentage',
    [step('opacity: 0.5:1')],
  ],
  [
    'a flicker opacity in exponent notation',
    '@keyframes crt-flicker sets opacity 1e-1, not a number from 0 to 1 or a percentage',
    [step('opacity: 1e-1')],
  ],
  [
    'a flicker that sets no opacity',
    '@keyframes crt-flicker sets no opacity',
    [swap(FLICKER, '@keyframes crt-old {\n'), append('@keyframes crt-flicker {\n  0% {\n  }\n}\n')],
  ],
  [
    'the flicker keyframes renamed away',
    '@keyframes crt-flicker is defined 0 times, not once',
    [swap(FLICKER, '@keyframes crt-flick {\n')],
  ],
  [
    'the flicker pointed at other keyframes',
    '  --color-text on --color-bg, flickering: 1.00:1, below 4.5:1',
    [swap(NAMED, 'animation: crt-dim '), append(deep('crt-dim', '0'))],
  ],
  ['a second crt-flicker block', TWO_BLOCKS, [append(deep('crt-flicker', '0.4'))]],
  [
    'a second crt-flicker block under -webkit-',
    TWO_BLOCKS,
    [append(`@-webkit-${deep('crt-flicker').slice(1)}`)],
  ],
  [
    'a second crt-flicker block in capitals',
    TWO_BLOCKS,
    [append(deep('crt-flicker').replace('@keyframes', '@KEYFRAMES'))],
  ],
  ['a second crt-flicker block, its name quoted', TWO_BLOCKS, [append(deep('"crt-flicker"'))]],
  [
    'a second crt-flicker block, its quoted name escaped',
    ESCAPED,
    [append(deep('"crt\\-flicker"'))],
  ],
  [
    'a second crt-flicker block, its quoted name in hex escapes',
    ESCAPED,
    [append(deep('"crt\\00002Dfl\\69 cker"'))],
  ],
  [
    'a second crt-flicker block, its quoted name continued over a line',
    ESCAPED,
    [append(deep('"crt-\\\nflicker"'))],
  ],
  [
    'a second crt-flicker block, its quoted name right after @keyframes',
    TWO_BLOCKS,
    [append(deep('"crt-flicker"').replace('@keyframes "', '@keyframes"'))],
  ],
  [
    'a second crt-flicker block, its single-quoted name continued over a line',
    ESCAPED,
    [append(deep("'crt-\\\nflicker'"))],
  ],
  [
    'a second crt-flicker block, its single-quoted name right after @keyframes',
    TWO_BLOCKS,
    [append(deep("'crt-flicker'").replace("@keyframes '", "@keyframes'"))],
  ],
  [
    'a second crt-flicker block with two spaces before its name',
    TWO_BLOCKS,
    [append(deep('crt-flicker').replace('@keyframes ', '@keyframes  '))],
  ],
  [
    'a second crt-flicker block with no space before its brace',
    TWO_BLOCKS,
    [append(deep('crt-flicker').replace('crt-flicker {', 'crt-flicker{'))],
  ],
  [
    'a second crt-flicker block closed right after its last step',
    TWO_BLOCKS,
    [append(deep('crt-flicker').replace('  }\n}\n', '  }}\n'))],
  ],
  [
    'a second flicker rule naming a deep animation',
    NAMES_TWO,
    [
      append(
        rule('[data-flicker="on"] .crt-content', 'animation: crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    "a deep animation named by [data-flicker='on']",
    NAMES_TWO,
    [
      append(
        rule("[data-flicker='on'] .crt-content", 'animation: crt-deep 0.15s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    'a deep animation named by -webkit-animation',
    NAMES_TWO,
    [
      append(
        rule('[data-flicker="on"] .crt-content', '-webkit-animation: crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    'a deep animation whose name is quoted',
    NAMES_TWO,
    [
      append(
        rule('[data-flicker="on"] .crt-content', 'animation-name: "crt-deep"') + deep('"crt-deep"'),
      ),
    ],
  ],
  [
    'a deep animation named by [DATA-FLICKER="on"]',
    NAMES_TWO,
    [
      append(
        rule('[DATA-FLICKER="on"] .crt-content', 'animation: crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    'a deep animation named by [data-flicker=on], unquoted',
    NAMES_TWO,
    [
      append(
        rule('[data-flicker=on] .crt-content', 'animation: crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    'a deep animation named by a flicker rule inside @media',
    NAMES_TWO,
    [
      append(
        '@media (min-width: 1px) {\n' +
          rule('[data-flicker="on"] .crt-content', 'animation: crt-deep 1s infinite') +
          `}\n${deep('crt-deep')}`,
      ),
    ],
  ],
  [
    'a deep animation named with no space after the colon',
    NAMES_TWO,
    [
      append(
        rule('[data-flicker="on"] .crt-content', 'animation:crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    'a deep animation named by [ data-flicker = "on" ], spaced',
    NAMES_TWO,
    [
      append(
        rule('[ data-flicker = "on" ] .crt-content', 'animation: crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    'a deep animation whose name ends in a digit',
    NAMES_TWO,
    [
      append(
        rule('[data-flicker="on"] .crt-content', 'animation: crt-deep2 1s infinite') +
          deep('crt-deep2'),
      ),
    ],
  ],
  [
    'a deep animation named by ANIMATION in capitals',
    NAMES_TWO,
    [
      append(
        rule('[data-flicker="on"] .crt-content', 'ANIMATION: crt-deep 1s infinite') +
          deep('crt-deep'),
      ),
    ],
  ],
  [
    'an animation named through var()',
    `the [data-flicker="on"] rules hold var(--case-animation), ${NOT_A_NAME}`,
    [
      define('  --case-animation: crt-deep;\n'),
      append(rule('[data-flicker="on"] .crt-content', 'animation-name: var(--case-animation)')),
    ],
  ],
  [
    'a deep animation named by a time glued to its quoted name',
    `the [data-flicker="on"] rules hold 1s"crt-deep", ${NOT_A_NAME}`,
    [
      append(
        rule('[data-flicker="on"] .crt-content', 'animation: 1s"crt-deep"') + deep('crt-deep'),
      ),
    ],
  ],

  // A comment opener inside a string opens no comment, and a brace there opens or closes nothing,
  // so the code after it is still checked. A backslash, a string its line ends and url( are
  // refused outright, since CSS reads each by rules of its own: where one would shift where a
  // string or a comment ends, the case quotes that refusal.
  [
    'a literal colour after a string holding /*',
    LITERAL_TEXT,
    block('  content: "/*";\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after a single-quoted string holding /*',
    LITERAL_TEXT,
    block("  content: '/*';\n  color: #333333;\n  /* */\n"),
  ],
  [
    'a literal colour after a url() holding /*',
    URL_CALL,
    block('  cursor: url(/*), auto;\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after an escaped solidus',
    ESCAPED,
    block('  x\\/* ;\n  color: #333333;\n  */\n'),
  ],
  [
    'a literal colour after a quote never closed and a string holding /*',
    UNCLOSED,
    block('  content: "x\n  ;\n  content: "/*";\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after a string holding an escaped quote and /*',
    ESCAPED,
    block('  content: "a\\"/*";\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after a url() holding an escaped bracket and /*',
    URL_CALL,
    block('  cursor: url(a\\)/*), auto;\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after a quoted url() holding a bracket and /*',
    URL_CALL,
    block('  cursor: url("a)/*"), auto;\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after a url() whose value follows a space',
    URL_CALL,
    block('  cursor: url( a/*), auto;\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after a quote that a carriage return ends',
    UNCLOSED,
    block('  content: "x\r  ;\r  content: "/*";\r  color: #333333;\r  /* */\n'),
  ],
  [
    'a literal colour after a quote that a form feed ends',
    UNCLOSED,
    block('  content: "x\f  ;\f  content: "/*";\f  color: #333333;\f  /* */\n'),
  ],
  [
    'a literal colour after a string holding }',
    LITERAL_TEXT,
    block('  content: "}";\n  color: #333333;\n'),
  ],
  [
    'a literal colour after a url() holding }',
    URL_CALL,
    block('  cursor: url(a}b), auto;\n  color: #333333;\n'),
  ],
  [
    'a literal colour after a URL() in capitals holding /*',
    URL_CALL,
    block('  cursor: URL(/*), auto;\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after a quoted url() spaced before its string, holding a bracket and /*',
    URL_CALL,
    block('  cursor: url( "a)/*"), auto;\n  color: #333333;\n  /* */\n'),
  ],
  [
    'a literal colour after a single-quoted url() holding a bracket and /*',
    URL_CALL,
    block("  cursor: url('a)/*'), auto;\n  color: #333333;\n  /* */\n"),
  ],
  [
    'a literal colour after a string holding a semicolon and }',
    LITERAL_TEXT,
    block('  content: ";}";\n  color: #333333;\n'),
  ],
  [
    'a literal colour after a string ending in an escaped backslash',
    ESCAPED,
    block('  content: "\\\\";\n  color: #333333;\n'),
  ],
  [
    'a literal colour right after a url()',
    URL_CALL,
    block('  cursor: url(x);\n  color: #333333;\n'),
  ],
  ['a literal colour right after a comment', LITERAL_TEXT, block('  /* note */color: #333333;\n')],
  [
    'a literal colour after two quotes that carriage returns end',
    UNCLOSED,
    block('  content: "x\r  ;\r  content: "y\r  ;\r  color: #333333;\r  /* */\n'),
  ],
  [
    'a quote never closed at the end of a sheet with no last line ending',
    UNCLOSED,
    [(css) => `${css}.case {\n  content: "x`],
  ],
  [
    'a function whose name ends in url, holding a string',
    URL_CALL,
    own('grid-area: xurl(1 ")")', 'color: var(--color-bg)'),
  ],
  [
    'a url() never closed at the end of a sheet with no last line ending',
    URL_CALL,
    [(css) => `${css}.case {\n  cursor: url(x`],
  ],

  // Legitimate forms the check must accept.
  ['a flicker opacity as a percentage', null, [step('opacity: 96%')]],
  [
    'a flicker rule with its timing written out',
    null,
    [
      swap(
        'animation: crt-flicker 0.15s infinite;',
        'animation: crt-flicker 0.15s steps(4, end) -0.5s 2 alternate both;',
      ),
    ],
  ],
  ['a transition eased by a keyword', null, own('transition: color 1s ease-in-out')],
  ['a token background with !important', null, own('background: var(--color-bg) !important')],
  ['a token with ! important, spaced', null, own('color: var(--color-text) ! important')],
  ['a token with !IMPORTANT in capitals', null, own('color: var(--color-text) !IMPORTANT')],
  ['color: inherit', null, own('color: inherit')],
  [
    "text in the parent's colour on no background of its own",
    null,
    own('color: inherit', 'background: transparent'),
  ],
  [
    'a fill in the text colour over a measured pair',
    null,
    own('-webkit-text-fill-color: currentColor', ...ON_BG),
  ],
  ['a token with a keyword fallback', null, own('color: var(--color-text, inherit)')],
  ['a border in currentColor', null, own('border: 1px solid currentColor')],
  [
    'a gradient of tokens',
    null,
    own('background: linear-gradient(var(--color-bg), var(--color-surface))'),
  ],
  ['a string holding {', null, own('content: "{"')],
  ['a string holding a semicolon and a colour', null, own('content: "; color: #333333"')],
  ['a sheet that opens with @charset', null, [(css) => `@charset "utf-8";\n${css}`]],
  ['an escape inside a string', ESCAPED, own('content: "\\201C"')],
  ['a background clipped to its padding', null, own('background-clip: padding-box')],
  ['text with no border image', null, own(...ON_BG, 'border-image: none')],
  [
    'text with no border image, in capitals and marked !important',
    null,
    own(...ON_BG, 'BORDER-IMAGE: NONE !important'),
  ],
  ['a byte order mark that opens the sheet', null, [(css) => `\ufeff${css}`]],
  [
    'characters outside ASCII in a string and a comment',
    null,
    own('content: "\u2192 \u00e9"', '/* \u00a0 \u00e9 */ order: 1'),
  ],
  [
    'a tab between a property and its value',
    null,
    own('border:\t1px solid var(--color-field-border)'),
  ],
  [
    'a block whose name CSS reads as two tokens is no flicker block',
    null,
    [append(deep('1s"crt-flicker"', '0.05'))],
  ],
  [
    'text with no background image',
    null,
    own('color: var(--color-text)', 'background: var(--color-bg)', 'background-image: none'),
  ],
  ['a size declared twice, as a fallback', null, own('height: 100vh', 'height: 100dvh')],
  ['a declaration with no colon', null, own('colorx')],
  [
    'an attribute selector holding @property',
    null,
    [append('[data-case="@property"] .x {\n  order: 1;\n}\n')],
  ],
  ['an at-rule holding declarations only', null, [append('@page {\n  margin: 1cm;\n}\n')]],
  ['a comment opened with /*/', null, block('  /*/ color: #333333; */\n')],
  ['a comment never closed at the end of the sheet', null, [(css) => `${css}/* never closed`]],
  [':root with no space before its brace', null, [(css) => css.replace(/^:root \{/, ':root{')]],
  [
    'a token with no space after its colon and one before its semicolon',
    null,
    [(css) => css.replace(/\n {2}--color-text: ([^;]*);/, '\n  --color-text:$1 ;')],
  ],
  ['a token in capital hex', null, [token('--color-text', '#E2E8F0')]],
  [
    'text on a tint written without spaces, to two decimals',
    null,
    own(
      'color: var(--color-text)',
      'background: color-mix(in srgb,var(--color-accent) 8.25%,transparent)',
    ),
  ],
  [
    'text on a tint with two spaces between in and srgb',
    null,
    own(
      'color: var(--color-text)',
      'background: color-mix(in  srgb, var(--color-accent) 8%, transparent)',
    ),
  ],
  [
    'text on a tint in capitals',
    null,
    own(
      'color: var(--color-text)',
      'background: COLOR-MIX(IN SRGB, var(--color-accent) 8%, TRANSPARENT)',
    ),
  ],
  [
    'text on a tint marked !important',
    null,
    own('color: var(--color-text)', `background: ${mix('--color-accent', 8)} !important`),
  ],
  [
    'text on a token as background-color',
    null,
    own('color: var(--color-text)', 'background-color: var(--color-bg)'),
  ],
  [
    'text with no background image, in capitals and marked !important',
    null,
    own(...ON_BG, 'background-image: NONE !important'),
  ],
  ['text with paint-order fill', null, own(...ON_BG, 'paint-order: fill')],
  ['a text cursor', null, own('cursor: text')],
  ['a string holding @import', null, own('content: "@import"')],
  [
    'a pulse tint with two spaces before its percentage',
    null,
    [
      append(
        keyframes(
          'case-pulse',
          'background: color-mix(in srgb, var(--color-urgency-high)  25%, transparent)',
          '50%',
        ),
      ),
    ],
  ],
  [
    'a pulse tint in capitals',
    null,
    [
      append(
        keyframes(
          'case-pulse',
          'background: COLOR-MIX(IN SRGB, var(--color-urgency-high) 25%, TRANSPARENT)',
          '50%',
        ),
      ),
    ],
  ],
  [
    'a gradient of two tints',
    null,
    own(
      `background-image: linear-gradient(${mix('--color-accent', 50)}, ${mix('--color-bg', 50)})`,
    ),
  ],
  [
    'a gradient of tokens each with a keyword fallback',
    null,
    own(
      'background-image: linear-gradient(var(--color-bg, transparent), ' +
        'var(--color-surface, transparent))',
    ),
  ],
  [
    'a flicker rule naming its animation single-quoted',
    null,
    [swap('animation: crt-flicker 0.15s infinite;', "animation: 'crt-flicker' 0.15s infinite;")],
  ],
  [
    'a flicker rule whose animation is !important',
    null,
    [
      swap(
        'animation: crt-flicker 0.15s infinite;',
        'animation: crt-flicker 0.15s infinite !important;',
      ),
    ],
  ],
  ['a flicker step setting OPACITY, spaced before its colon', null, [step('OPACITY : 0.96')]],
  ['a flicker opacity as a percentage to two decimals', null, [step('opacity: 96.25%')]],
  [
    'a rule before the :root block',
    null,
    [(css) => `.case-first {\n  color: var(--color-text);\n}\n${css}`],
  ],
  [
    'a rule in @media whose last declaration has no semicolon',
    null,
    [
      append(
        '@media (min-width: 1px) {\n.case {\n  color: var(--color-text);\n' +
          '  background: var(--color-bg)\n}\n}\n',
      ),
    ],
  ],
  [
    'the check run without a path reads the dashboard stylesheet',
    { passes: 'contrast: all 220 pairs clear the floor' },
    null,
  ],
  ['every word and unit a painting value may hold', null, [append(EVERY_WORD)]],
  [
    "every keyword and form of time a flicker rule's animation may hold",
    null,
    [swap('animation: crt-flicker 0.15s infinite;', EVERY_TIMING)],
  ],
  ['color: currentColor', null, own('color: currentColor')],
  [
    'text on each keyword that paints no background',
    null,
    [
      append(
        ['transparent', 'NONE', 'inherit']
          .map((k, i) => rule(`.case-${i}`, 'color: var(--color-text)', `background: ${k}`))
          .join(''),
      ),
    ],
  ],
];

// [what, [text, whether the view must hold it], edits]: what the rules read.
const views = [
  [
    'the view keeps the code after a string holding /*',
    ['"/*";\n  order: 7;', true],
    block('  content: "/*";\n  order: 7;\n  /* */\n'),
  ],
  [
    'the view drops a byte order mark that opens the sheet',
    ['\ufeff', false],
    [(css) => `\ufeff${css}`],
  ],
  [
    'the view ends a quote never closed at its line',
    ['"/*";\n  order: 7;', true],
    block('  content: "x\n  ;\n  content: "/*";\n  order: 7;\n  /* */\n'),
  ],
  ['the view leaves out a comment', ['case note', false], block('  /* case note */\n')],
  ['the view blanks a brace inside a string', ['content: " ";', true], own('content: "{"')],
];

// A reason is given when the output holds it, at the start of a line if it opens with two spaces.
const gives = (output, reason) =>
  reason.startsWith('  ')
    ? output.split('\n').some((line) => line.startsWith(reason))
    : output.includes(reason);

const pick = process.argv[2] === '--case' ? process.argv[3] : undefined;
const chosen = (list) => list.filter(([what]) => pick === undefined || what === pick);
const total = chosen(cases).length + chosen(views).length;
if (total === 0) {
  console.log(`contrast self-test: no case is called ${JSON.stringify(pick)}`);
  process.exit(1);
}

const dir = mkdtempSync(join(tmpdir(), 'contrast-self-test-'));
const copy = join(dir, 'tokens.css');
// Edits of null run the check with no path, as the loop does, on the dashboard's own stylesheet.
const run = (edits, ...flags) => {
  if (edits !== null) {
    writeFileSync(
      copy,
      edits.reduce((css, edit) => edit(css), source),
    );
  }
  // A check that never ends fails its case after ten seconds rather than stall the loop.
  const result = spawnSync(
    process.execPath,
    [checker, ...flags, ...(edits === null ? [] : [copy])],
    {
      encoding: 'utf8',
      timeout: 10000,
    },
  );
  if (result.status === null) {
    throw new Error(`the check did not finish (${result.signal ?? result.error})`);
  }
  return { status: result.status, output: result.stdout + result.stderr };
};
const first = (output) => output.trim().split('\n').slice(0, 2).join(' / ');
let bad = 0;
const report = (what, judge) => {
  let problem;
  try {
    problem = judge();
  } catch (error) {
    problem = error.message;
  }
  if (problem) bad += 1;
  console.log(`${problem ? 'FAIL' : 'ok'}: ${what}${problem ? `: ${problem}` : ''}`);
};
try {
  for (const [what, reason, edits] of chosen(cases)) {
    report(what, () => {
      const { status, output } = run(edits);
      if (reason === null || reason.passes) {
        if (status !== 0) return `the check refused a legitimate form: ${first(output)}`;
        return reason === null || output.includes(reason.passes)
          ? null
          : `the check passed, but without ${JSON.stringify(reason.passes)}: ${first(output)}`;
      }
      if (status === 0) return 'the check passed a form it must refuse';
      return gives(output, reason)
        ? null
        : `the check refused it, but not with ${JSON.stringify(reason)}: ${first(output)}`;
    });
  }
  for (const [what, [text, held], edits] of chosen(views)) {
    report(what, () => {
      const { status, output } = run(edits, '--show');
      if (status !== 0) return `--show failed: ${first(output)}`;
      return output.includes(text) === held
        ? null
        : `the view ${held ? 'lacks' : 'holds'} ${JSON.stringify(text)}`;
    });
  }
} finally {
  rmSync(dir, { recursive: true, force: true });
}
if (bad > 0) {
  console.log(`contrast self-test: ${bad} of ${total} cases misbehaved`);
  process.exit(1);
}
console.log(`contrast self-test: ${total === 1 ? 'the case' : `all ${total} cases`} behaved`);
