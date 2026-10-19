#!/usr/bin/env node
// contrast-check.mjs :: holds the dashboard theme to WCAG 2.2 AA, run by verify.sh.
// Usage: node scripts/contrast-check.mjs [--show] [path to tokens.css]
//
// It reads the token values from the stylesheet's first :root block, so a changed colour is
// measured the moment it changes. Every text token must reach 4.5:1 on every surface the
// dashboard paints: the screen's surfaces and the bulkhead chrome. Every rule that sets both a
// text colour and a background must reach it too, a translucent tint being composited over each
// surface the rule can sit on: the screen's, and the chrome's for the header, navigation and
// sign-in rules. So must the text an animated banner shows over its tint at the peak, body and
// muted text and the tint's own colour, on the page background it sits on.
// Form-field edges must reach 3:1 against every surface; the focus ring is the accent, which
// reaches the 4.5:1 of text there already.
// The opt-in flicker fades the whole screen over the chrome, to the lowest opacity reached by the
// one @keyframes block, written in any case and with -webkit- or without, that its
// [data-flicker="on"] rules name, quoted or not, through animation or animation-name, with
// -webkit- or without; each word there must be a keyword, a time, a count or a name, a quoted one
// too. That block may change opacity only, and the text pairs are measured at its lowest as well.
// Behind body text the scanlines only darken the background, which cannot lower a ratio for
// light text; over the large readouts (page headings and the dashboard counts) they darken both,
// and those must keep the large-text floor, 3:1, at --scanline-alpha. Finally, the phosphor
// accent must stand apart from every status colour, by at least 0.2 in the OKLab colour space, or
// decoration would read as health or alarm.
// Blending is in sRGB, as browsers composite. It fails closed. A value it cannot resolve fails,
// and so does a sheet that CSS would read otherwise than the rules here do: a backslash outside a
// comment, which CSS reads as an escape; a string its line ends before it closes; url(, whose
// unquoted form CSS reads as one token; a brace or semicolon inside brackets, which CSS reads as
// part of them; a character other than printable ASCII, a tab or a line ending outside a string
// or a comment, which CSS reads as part of a name or as a delimiter where the rules here might
// read a space, as in a no-break space; a block nested in a rule, or never closed; an at-rule
// holding declarations beside blocks, which @scope and @page apply and the rules here never read;
// a painting property or a token declared twice in one rule, where CSS paints the last, or the
// last marked !important; a rule that sets both background and background-color; an @import,
// whose sheet the check never reads; and an @property, which can give a token another value below
// :root than the one read here. So does cubic-bezier( or linear(, an easing that can carry an
// animation or a transition past its keyframes or its end colours, where no check measures it.
// Outside the first :root block a custom property fails, since nothing would measure it, and in
// any rule, :root's own declarations among them, so does a colour of the rule's own in any
// property that paints one, with any vendor prefix or none: text and its fill and stroke,
// background and its image, border, each of its sides and its image, outline, column rule, list
// marker image, fill and stroke, stop, flood and lighting colours, a font palette's colours, and
// caret, accent, tap highlight, decoration, emphasis and scrollbar colours. Each word of such a
// value must be a :root token, a tint of one, color-mix(in srgb, var(--token) N%, transparent) at
// 0% to 100%, a gradient built from those, a length or a keyword; initial, unset, revert and auto
// are not among the keywords, since each can bring back a colour of the browser's own; nor is
// all, which sets every colour a rule paints at once. Text is painted in color, which must be a
// token, since a tint of one is never measured, or inherit or currentColor, which take the
// parent's colour; -webkit-text-fill-color may only be one of those two keywords, since an
// element's children inherit a fill over their own colour. A token that is not one of the text
// tokens needs a background of its own in the rule, where the pair is measured. A rule that
// pairs text with a background other than a token, a tint of one, transparent, none or inherit
// fails, since that pair is never measured either; so does a rule with text in a token, or in the
// parent's colour by keyword, that paints a background image under it, or sets any border image
// but none, whose middle can be painted under the text; so does a rule whose text takes the
// parent's colour by keyword over a background of its own, where nothing measures the pair; so
// does any rule that clips its background to the text, or through a token, which can do the
// same; and so does a mix in a @keyframes block that is not a tint. Shadows and masks are
// decorative shading and are not checked, and the colours of borders, outlines, strokes and the
// like are held to the tokens but measured only as the field edge and the focus ring above.
// What it cannot see: it reads this one stylesheet; it does not follow the cascade, so a
// background, background image or border image set in a rule that sets no text colour of its
// own, such as a button's hover plate, or a keyframe's colour other than a tint, is measured only
// where it is one of the surfaces above, under every text token; it does not model opacity,
// filters or blending outside the flicker's keyframes, a disabled button's 0.4 among them, which
// WCAG exempts, nor text drawn in SVG, whose colour is a fill, nor an image in content or a
// cursor, nor a shadow drawn inside a box, which can cover its background, nor the browser's own
// colours where no rule sets one, such as a field's own border, which color-scheme switches and
// may only switch in :root; and it knows the flicker only by [data-flicker="on"] in a selector,
// quoted or not, so another selector for the attribute, such as [data-flicker~="on"] or one
// flagged i, it does not see.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const args = process.argv.slice(2);
const path =
  args.find((a) => a !== '--show') ??
  fileURLToPath(new URL('../frontend/src/styles/tokens.css', import.meta.url));

// The stylesheet as the rules read it, which --show prints. Each comment becomes a space, as CSS
// reads one, and a string is kept whole, each brace and semicolon in it made a space, since there
// it opens, closes and ends nothing; a "/*" in a string opens no comment. A leading byte order
// mark is dropped, as CSS drops it, and a comment never closed runs to the end of the sheet, as
// in CSS. Brackets, ( and [, each close only at their own closer. The forms CSS reads by rules
// this reading does not have are refused, each naming its line:
//   a backslash anywhere outside a comment, which CSS reads as an escape, the character it stands
//     for, inside a string as well;
//   a string its line or the sheet ends before its closing quote, which CSS reads otherwise;
//   url(, whose unquoted form CSS reads as one token, quotes, brackets and comment marks in it;
//   cubic-bezier( and linear(, easings that can carry an animation or a transition past its
//     keyframes or its end colours, where no check measures it;
//   a brace or semicolon inside brackets, which CSS reads as part of them;
//   and a character other than printable ASCII, a tab or a line ending outside a string or a
//     comment, read by CSS as part of a name or a delimiter where this reading might see a space.
const INERT = /[{};]/g;
const URL_CALL = /url\(/iy;
const EASING_CALL = /cubic-bezier\(|linear\(/iy;
const escapes = [];
const unclosed = [];
const urls = [];
const easings = [];
const bracketed = [];
const foreign = [];
function withoutComments(text) {
  let out = '';
  const closers = [];
  const line = (i) => text.slice(0, i).split('\n').length;
  // Each list names a line once.
  const note = (list, i) => {
    if (list.at(-1) !== line(i)) list.push(line(i));
  };
  for (let i = 0; i < text.length; ) {
    let j = i + 1;
    let quoted = false;
    URL_CALL.lastIndex = i;
    EASING_CALL.lastIndex = i;
    if (text[i] === '\\') {
      note(escapes, i);
    } else if (text[i] === '"' || text[i] === "'") {
      while (j < text.length && text[j] !== text[i] && text[j] !== '\n') {
        if (text[j] === '\\') note(escapes, j);
        j += 1;
      }
      if (text[j] !== text[i]) note(unclosed, i);
      j += 1;
      quoted = true;
    } else if (URL_CALL.test(text)) {
      note(urls, i);
    } else if (EASING_CALL.test(text)) {
      note(easings, i);
    } else if (text.startsWith('/*', i)) {
      const end = text.indexOf('*/', i + 2);
      out += ' ';
      i = end === -1 ? text.length : end + 2;
      continue;
    } else if (text[i] === '(' || text[i] === '[') {
      closers.push(text[i] === '(' ? ')' : ']');
    } else if (text[i] === closers.at(-1)) {
      closers.pop();
    } else if (closers.length && '{};'.includes(text[i])) {
      note(bracketed, i);
    } else if (/[^\t\n -~]/.test(text[i])) {
      note(foreign, i);
    }
    out += quoted ? text.slice(i, j).replace(INERT, ' ') : text.slice(i, j);
    i = j;
  }
  return out;
}
const css = withoutComments(
  readFileSync(path, 'utf8')
    .replace(/^\uFEFF/, '')
    .replace(/\r\n?|\f/g, '\n'),
);
if (args.includes('--show')) {
  process.stdout.write(css);
  process.exit(0);
}

const rootBlock = css.match(/:root\s*\{([^}]*)\}/);
if (!rootBlock) {
  console.error(`contrast: no :root block in ${path}`);
  process.exit(1);
}
const tokens = new Map();
for (const [, name, value] of rootBlock[1].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
  tokens.set(name, value.trim());
}

function resolve(name, seen = new Set()) {
  if (seen.has(name)) throw new Error(`${name} refers to itself`);
  seen.add(name);
  const value = tokens.get(name);
  if (value === undefined) throw new Error(`${name} is not a token in :root`);
  const ref = value.match(/^var\((--[\w-]+)\)$/);
  if (ref) return resolve(ref[1], seen);
  const hex = value.match(/^#([0-9a-f]{6})$/i);
  if (!hex) throw new Error(`${name} is ${value}, not an opaque #rrggbb colour`);
  return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16));
}

const channel = (c) => {
  const v = c / 255;
  return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
};
const luminance = ([r, g, b]) => 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
const ratio = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
// A colour at the given opacity over an opaque one.
const over = (top, alpha, under) => top.map((c, i) => c * alpha + under[i] * (1 - alpha));
// Perceptual distance in OKLab (Bjorn Ottosson's matrices), from linear sRGB.
const oklab = (rgb) => {
  const [r, g, b] = rgb.map(channel);
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b);
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b);
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b);
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ];
};
const apart = (a, b) => Math.hypot(...oklab(a).map((v, i) => v - oklab(b)[i]));

const TEXT = [
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
const SCREEN = [
  '--color-bg',
  '--color-surface',
  '--color-surface-elevated',
  '--color-surface-hover',
];
const CHROME = ['--color-chrome', '--color-chrome-top', '--color-chrome-bottom'];
// A field's edge. The focus ring is the accent, which TEXT holds to 4.5:1 on the same surfaces,
// above the 3:1 an edge needs.
const EDGES = ['--color-field-border'];
// Rules that render on the bulkhead chrome as well as, or instead of, the screen: those whose
// selector holds any of these.
const ON_CHROME = [
  '.app-header',
  '.app-nav',
  '.nav-link',
  '.brand-',
  '.display-toggle',
  '.logout-btn',
  '.login-',
  '.form-error',
];
const STATUS = [
  '--color-success',
  '--color-urgency-low',
  '--color-urgency-medium',
  '--color-error',
  '--color-urgency-high',
];
// The large readouts the scanlines cross, and what they sit on: headings on the screen, counts
// on their cards.
const READOUTS = [
  '--color-text',
  '--color-urgency-high',
  '--color-urgency-medium',
  '--color-urgency-low',
];
const READOUT_SURFACES = ['--color-bg', '--color-surface'];
// The text an animation's tint lies under, besides text in the tint's own colour: the firing
// banner's label and its muted line, over its rust FIRING and DISMISS.
const PULSE_TEXT = ['--color-text', '--color-text-muted'];

// The floors: WCAG 2.2 AA's 4.5:1 for text, and 3:1 for large text (1.4.3) and for a field's
// edge and the focus ring (1.4.11); and the least OKLab distance between the accent and a
// status colour.
const TEXT_FLOOR = 4.5;
const LARGE_FLOOR = 3;
const APART_FLOOR = 0.2;

const failures = [];
let pairs = 0;
function check(label, text, background, floor) {
  pairs += 1;
  const r = ratio(text, background);
  if (r < floor) failures.push(`${label}: ${r.toFixed(2)}:1, below ${floor}:1`);
}

// The properties a rule paints a colour with, each form by name, matched with any vendor prefix
// taken off (the last eight are the logical sides WebKit named, which Chromium still paints), and
// the words their values may hold: :root tokens (each var() is checked against them, its
// fallback with the rest), tints of them, the functions and keywords that build gradients from
// those, lengths, and keywords. A word outside these, such as a hex value, rgb(), oklab(), a mix
// other than a tint or any colour name, is a colour no check would measure.
const PAINT = new Set([
  'color',
  'background',
  'background-color',
  'background-image',
  'text-fill-color',
  'text-stroke',
  'text-stroke-color',
  'fill',
  'stroke',
  'stop-color',
  'flood-color',
  'lighting-color',
  'caret',
  'caret-color',
  'accent-color',
  'tap-highlight-color',
  'text-decoration',
  'text-decoration-color',
  'text-emphasis',
  'text-emphasis-color',
  'scrollbar-color',
  'column-rule',
  'column-rule-color',
  'outline',
  'outline-color',
  'list-style',
  'list-style-image',
  'border-image',
  'border-image-source',
  'override-colors',
  'border',
  'border-color',
  'border-top',
  'border-top-color',
  'border-right',
  'border-right-color',
  'border-bottom',
  'border-bottom-color',
  'border-left',
  'border-left-color',
  'border-block',
  'border-block-color',
  'border-block-start',
  'border-block-start-color',
  'border-block-end',
  'border-block-end-color',
  'border-inline',
  'border-inline-color',
  'border-inline-start',
  'border-inline-start-color',
  'border-inline-end',
  'border-inline-end-color',
  'border-start',
  'border-start-color',
  'border-end',
  'border-end-color',
  'border-before',
  'border-before-color',
  'border-after',
  'border-after-color',
]);
const VENDOR = /^-[a-z]+-/;
const WORDS = new Set([
  'transparent',
  'none',
  'inherit',
  'currentcolor',
  'solid',
  'dashed',
  'dotted',
  'double',
  'groove',
  'ridge',
  'inset',
  'outset',
  'hidden',
  'thin',
  'medium',
  'thick',
  'underline',
  'overline',
  'line-through',
  'wavy',
  'linear-gradient',
  'radial-gradient',
  'conic-gradient',
  'repeating-linear-gradient',
  'repeating-radial-gradient',
  'repeating-conic-gradient',
  'to',
  'at',
  'from',
  'top',
  'bottom',
  'left',
  'right',
  'center',
  'circle',
  'ellipse',
  'closest-side',
  'closest-corner',
  'farthest-side',
  'farthest-corner',
  'no-repeat',
  'repeat',
  'repeat-x',
  'repeat-y',
  'cover',
  'contain',
  'fixed',
  'scroll',
  'local',
  'border-box',
  'padding-box',
  'content-box',
  'filled',
  'open',
  'dot',
  'double-circle',
  'triangle',
  'sesame',
  'stretch',
  'round',
  'space',
  'fill',
]);
const NUMBER = /^-?\d*\.?\d+(px|rem|em|ch|ex|%|deg|turn|rad|vh|vw|vmin|vmax)?$/i;
const ACCEPTED =
  'accepted: var(--token), a tint color-mix(in srgb, var(--token) N%, transparent), a gradient ' +
  'of those, a length, transparent, none, currentColor or inherit, with or without !important';
const IMPORTANT = /!\s*important\s*$/i;
// The keywords a text colour may be instead of a token: each takes the parent's colour, a token
// measured where the parent's rule sets it. initial, unset and revert are not words here at all,
// since each can bring back a colour of the browser's own, which no check measures, and
// transparent hides the text.
const TEXT_KEYWORDS = /^(inherit|currentcolor)$/i;
// Text in such a keyword, as the rules below name it.
const INHERITED = 'inherited';
// The backgrounds a rule may set under text without painting one of its own.
const NO_BACKGROUND = /^(transparent|none|inherit)$/i;
// A value that is var() of one token, with any fallback; the token's name.
const TOKEN_VALUE = /^var\((--[\w-]+)(?:\s*,[^)]*)?\)$/;
const tokenOf = (value) => value?.replace(IMPORTANT, '').trim().match(TOKEN_VALUE)?.[1];
// A tint: a token mixed with transparent in sRGB, at 0% to 100%, which paints the token at that
// opacity. Mixes are measured, and allowed, in this form alone.
const TINT =
  String.raw`color-mix\(in srgb,\s*var\((--[\w-]+)\)\s+` +
  String.raw`(100|[1-9]?\d(?:\.\d+)?)%,\s*transparent\)`;
const TINT_VALUE = new RegExp(`^${TINT}$`, 'i');
const TINTS = new RegExp(TINT, 'gi');
const VAR = /var\(\s*(--[\w-]+)\s*(?:,([^()]*))?\)/;
function paintProblem(raw) {
  // Each tint becomes the var() of its token, so a mix in any other form is left as the word
  // color-mix, which is not one of the words.
  let value = raw.replace(IMPORTANT, '').replace(TINTS, ' var($1) ');
  for (let found = value.match(VAR); found; found = value.match(VAR)) {
    if (!tokens.has(found[1])) return `names ${found[1]}, which is not a :root token`;
    value = value.replace(found[0], ` TOKEN ${found[2] ?? ''} `);
  }
  const words = value.split(/[\s,()/]+/).filter(Boolean);
  const odd = words.find((w) => w !== 'TOKEN' && !WORDS.has(w.toLowerCase()) && !NUMBER.test(w));
  return odd ? `holds ${odd}, which no check measures (${ACCEPTED})` : null;
}

// The flicker: the one animation the [data-flicker="on"] rule names, defined by one @keyframes
// block that changes opacity only, a number or a percentage at each step.
const ANIMATION_WORDS = new Set([
  'none',
  'infinite',
  'linear',
  'ease',
  'ease-in',
  'ease-out',
  'ease-in-out',
  'step-start',
  'step-end',
  'normal',
  'reverse',
  'alternate',
  'alternate-reverse',
  'forwards',
  'backwards',
  'both',
  'running',
  'paused',
]);
const TIMING = /^[-+]?(\d*\.)?\d+(m?s)?$/i;
// A keyframes name: a word of letters, digits, hyphens and underscores, or a string, whole. A
// word in which CSS reads more than one token, such as 1s"crt-flicker", is no name to CSS or to
// this check.
const NAME = String.raw`(?:[-\w]+|"[^"]*"|'[^']*')`;
const ANIMATION_NAME = new RegExp(`^${NAME}$`);
// A keyframes name as CSS compares it, quotes off, so "crt-flicker" and crt-flicker are one name.
const cssName = (raw) => raw.replace(/^(["'])(.*)\1$/, '$2');
function flickerOpacity() {
  const names = new Set();
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    if (!/\[\s*data-flicker\s*=\s*(["']?)on\1\s*\]/i.test(selector)) continue;
    for (const [, value] of body.matchAll(
      /(?<![-\w])(?:-webkit-)?animation(?:-name)?\s*:\s*([^;]+)/gi,
    )) {
      // The timing functions, cubic-bezier(), steps() and linear(), go first, so the first and
      // the last are refused as easings rather than as names; each word left must be a
      // keyword, a time, a count or a name.
      const words = value
        .replace(IMPORTANT, '')
        .replace(/(?:cubic-bezier|steps|linear)\([^()]*\)/gi, ' ')
        .split(/[\s,]+/)
        .filter(Boolean);
      for (const w of words) {
        if (ANIMATION_WORDS.has(w.toLowerCase()) || TIMING.test(w)) continue;
        if (!ANIMATION_NAME.test(w)) {
          throw new Error(
            `the [data-flicker="on"] rules hold ${w}, which is not a keyword, a time, a count ` +
              'or a name',
          );
        }
        names.add(cssName(w));
      }
    }
  }
  if (names.size !== 1) {
    throw new Error(`the [data-flicker="on"] rules name ${names.size} animations, not one`);
  }
  const [name] = names;
  const blocks = [
    ...css.matchAll(
      new RegExp(
        String.raw`@(?:-webkit-)?keyframes(?:\s+|(?=["']))(${NAME})` +
          String.raw`\s*\{((?:[^{}]*\{[^{}]*\})*)\s*\}`,
        'gi',
      ),
    ),
  ].filter((block) => cssName(block[1]) === name);
  if (blocks.length !== 1) {
    throw new Error(`@keyframes ${name} is defined ${blocks.length} times, not once`);
  }
  const depths = [];
  for (const [, , body] of blocks[0][2].matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    for (const declaration of body
      .split(';')
      .map((d) => d.trim())
      .filter(Boolean)) {
      const [prop, ...rest] = declaration.split(':');
      const value = rest.join(':').trim();
      if (prop.trim().toLowerCase() !== 'opacity') {
        throw new Error(
          `@keyframes ${name} sets ${prop.trim()}; the flicker may change opacity only`,
        );
      }
      const percent = value.match(/^(\d*\.?\d+)%$/);
      const depth = percent
        ? Number(percent[1]) / 100
        : /^\d*\.?\d+$/.test(value)
          ? Number(value)
          : NaN;
      if (!(depth >= 0 && depth <= 1)) {
        throw new Error(
          `@keyframes ${name} sets opacity ${value}, not a number from 0 to 1 or a percentage`,
        );
      }
      depths.push(depth);
    }
  }
  if (depths.length === 0) throw new Error(`@keyframes ${name} sets no opacity`);
  return Math.min(...depths);
}

// The blocks of the sheet, as the rules here read them: a rule holds declarations only, and an
// at-rule holds declarations or rules, not both. A block nested in a rule, which CSS nesting
// applies to the rule's descendants, an at-rule holding declarations beside blocks, which @scope
// and @page apply and the rules here never read, and a block never closed, which CSS closes at the
// end of the sheet, would each keep declarations from the rules, so each fails, and so does an
// @import, whose sheet they never read.
function structure() {
  // Each open block: its prelude, and whether it holds declarations and blocks.
  const open = [];
  let start = 0;
  for (let i = 0; i < css.length; i += 1) {
    if (!'{};'.includes(css[i])) continue;
    const text = css.slice(start, i).trim().replace(/\s+/g, ' ');
    start = i + 1;
    const inner = open.at(-1);
    if (inner !== undefined && css[i] !== '{' && text) inner.declarations = true;
    if (css[i] === '{') {
      if (/^@property\b/i.test(text)) {
        failures.push(
          `${text}: registers a custom property, which can give a token another value below ` +
            ':root than the one this check reads',
        );
      }
      if (inner !== undefined && !inner.prelude.startsWith('@')) {
        failures.push(
          `${inner.prelude}: nests ${text} {...} in its block, which the rules here do not read: ` +
            'write it as a rule of its own',
        );
      }
      if (inner !== undefined) inner.blocks = true;
      open.push({ prelude: text, declarations: false, blocks: false });
    } else if (css[i] === '}') {
      const closed = open.pop();
      if (closed?.declarations && closed.blocks && closed.prelude.startsWith('@')) {
        failures.push(
          `${closed.prelude}: holds declarations beside blocks, which the rules here do not ` +
            'read: write the declarations as a rule of their own',
        );
      }
    } else if (/^@import\b/i.test(text)) {
      failures.push(`${text}: brings in a stylesheet this check does not read`);
    }
  }
  if (open.length) {
    failures.push(
      `${open.at(-1).prelude}: its block is never closed, and CSS closes it at the end of the ` +
        'sheet',
    );
  }
}

try {
  if (escapes.length) {
    failures.push(
      `line ${escapes.join(', ')}: a backslash, which CSS reads as an escape, the character it ` +
        'stands for, and this check would not: write the character plainly',
    );
  }
  if (unclosed.length) {
    failures.push(
      `line ${unclosed.join(', ')}: a string its line or the sheet ends before it closes, which ` +
        'CSS reads otherwise than this check: close it on its line',
    );
  }
  if (urls.length) {
    failures.push(
      `line ${urls.join(', ')}: url(, whose unquoted form CSS reads as one token, quotes, ` +
        'brackets and comment marks in it, and which brings in a file no check reads: take it out',
    );
  }
  if (easings.length) {
    failures.push(
      `line ${easings.join(', ')}: cubic-bezier( or linear(, an easing that can carry an ` +
        'animation or a transition past its keyframes or its end colours, where no check ' +
        'measures it: ease with a keyword or steps()',
    );
  }
  if (foreign.length) {
    failures.push(
      `line ${foreign.join(', ')}: a character other than printable ASCII outside a string or ` +
        'a comment, which CSS reads as part of a name or as a delimiter where this check might ' +
        'read a space: take it out',
    );
  }
  if (bracketed.length) {
    failures.push(
      `line ${bracketed.join(', ')}: a brace or semicolon inside brackets, which CSS reads as ` +
        'part of them and this check would not: take it out',
    );
  }
  structure();
  const FLICKER_OPACITY = flickerOpacity();

  for (const t of TEXT) {
    for (const s of [...SCREEN, ...CHROME])
      check(`${t} on ${s}`, resolve(t), resolve(s), TEXT_FLOOR);
    for (const s of SCREEN) {
      const frame = resolve('--color-chrome-top');
      const fade = (c) => over(c, FLICKER_OPACITY, frame);
      check(`${t} on ${s}, flickering`, fade(resolve(t)), fade(resolve(s)), TEXT_FLOOR);
    }
  }
  const alpha = Number(tokens.get('--scanline-alpha'));
  if (!(alpha >= 0 && alpha < 1)) {
    throw new Error(`--scanline-alpha is ${tokens.get('--scanline-alpha')}, not an opacity`);
  }
  const shade = (c) => c.map((v) => v * (1 - alpha));
  for (const t of READOUTS) {
    for (const s of READOUT_SURFACES) {
      check(
        `${t} readout on ${s}, under the scanlines`,
        shade(resolve(t)),
        shade(resolve(s)),
        LARGE_FLOOR,
      );
    }
  }
  for (const e of EDGES) {
    for (const s of [...SCREEN, ...CHROME])
      check(`${e} edge on ${s}`, resolve(e), resolve(s), LARGE_FLOOR);
  }

  // Each rule's own declarations: no custom property outside the first :root block, no colour of
  // the rule's own, each painting property and token declared once; and a text colour and a
  // background set together, measured as a pair. A rule's selector is what follows the last
  // brace or semicolon before its block, so a statement such as @charset is no part of it.
  let rules = 0;
  let tokenBlock = true;
  for (const [, selector, body] of css.matchAll(/([^{};]+)\{([^{}]*)\}/g)) {
    const where = selector.trim().replace(/\s+/g, ' ');
    // The first :root block holds the tokens; its other declarations are checked as any rule's.
    const tokensHere = tokenBlock && where === ':root';
    if (tokensHere) tokenBlock = false;
    const declared = new Map();
    for (const declaration of body
      .split(';')
      .map((d) => d.trim())
      .filter(Boolean)) {
      const at = declaration.indexOf(':');
      if (at < 1) continue;
      const prop = declaration.slice(0, at).trim().toLowerCase();
      const value = declaration
        .slice(at + 1)
        .trim()
        .replace(/\s+/g, ' ');
      const painting = PAINT.has(prop.replace(VENDOR, ''));
      if ((painting || prop.startsWith('--')) && declared.has(prop)) {
        failures.push(
          `${where}: declares ${prop} twice, where CSS paints the last, or the last marked ` +
            '!important, and the rules here may read another: declare it once',
        );
      }
      declared.set(prop, value);
      if (prop.startsWith('--')) {
        if (!tokensHere) {
          failures.push(
            `${where}: defines ${prop} outside the first :root block, where nothing measures it`,
          );
        }
      } else if (painting) {
        const problem = paintProblem(value);
        const bare = value.replace(IMPORTANT, '').trim();
        if (problem) failures.push(`${where}: ${prop} ${problem}`);
        else if (prop === 'color' && !TOKEN_VALUE.test(bare) && !TEXT_KEYWORDS.test(bare)) {
          failures.push(
            `${where}: color is ${bare}, a text colour no check measures: use a :root token`,
          );
        } else if (prop === '-webkit-text-fill-color' && !TEXT_KEYWORDS.test(bare)) {
          failures.push(
            `${where}: -webkit-text-fill-color is ${bare}, a fill the element's children ` +
              'inherit over their own colour, so the colour measured need not be the one ' +
              'painted: set color instead',
          );
        }
      } else if (prop === 'color-scheme' && !tokensHere) {
        failures.push(
          `${where}: color-scheme ${value} outside the first :root block switches the ` +
            "browser's own colours below it, which no check measures",
        );
      } else if (prop === 'all') {
        failures.push(
          `${where}: all ${value} sets every colour the rule paints to a value no check ` +
            'measures',
        );
      } else if (prop.replace(VENDOR, '') === 'background-clip' && /\btext\b|var\(/i.test(value)) {
        failures.push(
          `${where}: ${prop} ${value} can paint the text with the background, ` +
            'which no check measures',
        );
      }
    }
    if (declared.has('background') && declared.has('background-color')) {
      failures.push(
        `${where}: sets both background and background-color, of which CSS paints the last ` +
          'and the rules here would read one: set the colour once',
      );
    }
    // The colour the text is painted in: its token, or, where the rule gives the colour or the
    // fill as a keyword, the parent's colour, which is measured where the parent's rule sets it
    // but never on this rule's own background, image or border image. A rule that sets neither
    // leaves its text to the cascade.
    const keyword = ['color', '-webkit-text-fill-color'].some((p) =>
      TEXT_KEYWORDS.test(declared.get(p)?.replace(IMPORTANT, '').trim() ?? ''),
    );
    const text = tokenOf(declared.get('color')) ?? (keyword ? INHERITED : undefined);
    if (!text) continue;
    const image = declared.get('background-image')?.replace(IMPORTANT, '').trim();
    if (image !== undefined && image.toLowerCase() !== 'none') {
      failures.push(
        `${where}: paints ${text} text over a background image, which no check measures`,
      );
      continue;
    }
    // Any border image but none can paint its middle under the text: where its slice says fill,
    // always for -webkit-border-image, and through a token either way.
    const framed = [...declared].find(
      ([p, v]) =>
        /^border-image/.test(p.replace(VENDOR, '')) &&
        v.replace(IMPORTANT, '').trim().toLowerCase() !== 'none',
    );
    if (framed) {
      failures.push(
        `${where}: paints ${text} text with a border image (${framed[0]} ${framed[1]}), which ` +
          'can paint under it and which no check measures',
      );
      continue;
    }
    const value = (declared.get('background') ?? declared.get('background-color') ?? 'none')
      .replace(IMPORTANT, '')
      .trim();
    if (text === INHERITED) {
      if (!NO_BACKGROUND.test(value)) {
        failures.push(
          `${where}: pairs inherited text with ${value}, a background no check measures: ` +
            'give the text a token',
        );
      }
      continue;
    }
    const solid = tokenOf(value);
    const tint = value.match(TINT_VALUE);
    if (solid) {
      check(`${where}: ${text} on ${solid}`, resolve(text), resolve(solid), TEXT_FLOOR);
    } else if (tint) {
      const chrome = ON_CHROME.some((selector) => where.includes(selector));
      for (const s of chrome ? [...SCREEN, ...CHROME] : SCREEN) {
        const under = over(resolve(tint[1]), Number(tint[2]) / 100, resolve(s));
        check(
          `${where}: ${text} on ${tint[2]}% ${tint[1]} over ${s}`,
          resolve(text),
          under,
          TEXT_FLOOR,
        );
      }
    } else {
      if (!NO_BACKGROUND.test(value)) {
        failures.push(
          `${where}: pairs ${text} with ${value}, a background no check measures: ` +
            'use a token or a tint of one',
        );
      } else if (!TEXT.includes(text)) {
        failures.push(
          `${where}: colours text with ${text}, which is not a text token, and sets no ` +
            'background to measure it on',
        );
      }
      continue;
    }
    rules += 1;
  }
  if (rules === 0)
    failures.push('no rule pairs a text colour with a background: the parser has drifted');

  // Animations: each tint a @keyframes block paints on the page background, under the text that
  // lies over it and text in the tint's own colour; a mix in any other form fails.
  let peaks = 0;
  for (const [, name, body] of css.matchAll(
    /@(?:-webkit-)?keyframes\s*([^{]*)\{((?:[^{}]*\{[^{}]*\})*)\s*\}/gi,
  )) {
    let tints = 0;
    for (const [, token, pct] of body.matchAll(TINTS)) {
      tints += 1;
      for (const t of [...PULSE_TEXT, token]) {
        const under = over(resolve(token), Number(pct) / 100, resolve('--color-bg'));
        check(
          `@keyframes: ${t} on ${pct}% ${token} over --color-bg`,
          resolve(t),
          under,
          TEXT_FLOOR,
        );
      }
    }
    if (tints !== (body.match(/color-mix\(/gi) ?? []).length) {
      failures.push(
        `@keyframes ${name.trim()}: mixes a colour other than as a tint, color-mix(in srgb, ` +
          'var(--token) N%, transparent), which no check measures',
      );
    }
    peaks += tints;
  }
  if (peaks === 0) failures.push('no animation tint found: the parser has drifted');

  const accent = resolve('--color-accent');
  for (const s of STATUS) {
    const d = apart(accent, resolve(s));
    if (d < APART_FLOOR)
      failures.push(
        `--color-accent is ${d.toFixed(3)} from the status colour ${s} in OKLab, ` +
          `below ${APART_FLOOR}`,
      );
  }
} catch (error) {
  console.error(`contrast: could not measure: ${error.message}`);
  process.exit(1);
}

if (failures.length) {
  console.log(`contrast: ${failures.length} of ${pairs} pairs fail:`);
  for (const failure of failures) console.log(`  ${failure}`);
  process.exit(1);
}
console.log(
  `contrast: all ${pairs} pairs clear the floor (text and the focus ring ${TEXT_FLOOR}:1, field ` +
    `edges and large readouts under the scanlines ${LARGE_FLOOR}:1), plain, flickering and ` +
    'animated; the accent stands apart from every status colour; every colour a rule paints ' +
    'comes from a token.',
);
