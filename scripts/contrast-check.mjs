#!/usr/bin/env node
// contrast-check.mjs :: holds the dashboard theme to WCAG 2.2 AA, run by verify.sh.
// Usage: node scripts/contrast-check.mjs [path to tokens.css]
//
// It reads the token values from the stylesheet's first :root block, so a changed colour is
// measured the moment it changes. Every text token must reach 4.5:1 on every surface the
// dashboard paints: the screen's surfaces and the bulkhead chrome. Every rule that sets both a
// text colour and a background must reach it too, a translucent tint being composited over each
// screen surface. Form-field edges and the focus ring must reach 3:1 against every surface.
// The opt-in flicker fades the whole screen to 96% over the chrome, and the text pairs are
// measured there as well. Behind body text the scanlines only darken the background, which
// cannot lower a ratio for light text; over the large readouts (page headings and the dashboard
// counts) they darken both, and those must keep the large-text floor, 3:1, at --scanline-alpha.
// Finally, the phosphor accent must not be a status colour, or decoration would read as health
// or alarm.
// Blending is in sRGB, as browsers composite. It fails closed: a value it cannot resolve fails.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const path = process.argv[2] ?? fileURLToPath(new URL('../frontend/src/styles/tokens.css', import.meta.url));
const css = readFileSync(path, 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

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

const TEXT = [
  '--color-text', '--color-text-muted', '--color-text-faint', '--color-accent',
  '--color-accent-strong', '--color-urgency-high', '--color-urgency-medium',
  '--color-urgency-low', '--color-error', '--color-success',
];
const SCREEN = ['--color-bg', '--color-surface', '--color-surface-elevated', '--color-surface-hover'];
const CHROME = ['--color-chrome', '--color-chrome-top', '--color-chrome-bottom'];
const EDGES = ['--color-field-border', '--color-accent'];
const STATUS = ['--color-success', '--color-urgency-low', '--color-error', '--color-urgency-high'];
// The large readouts the scanlines cross, and what they sit on: headings on the screen, counts
// on their cards.
const READOUTS = ['--color-text', '--color-urgency-high', '--color-urgency-medium', '--color-urgency-low'];
const READOUT_SURFACES = ['--color-bg', '--color-surface'];
const FLICKER_OPACITY = 0.96;

const failures = [];
let pairs = 0;
function check(label, text, background, floor) {
  pairs += 1;
  const r = ratio(text, background);
  if (r < floor) failures.push(`${label}: ${r.toFixed(2)}:1, below ${floor}:1`);
}

try {
  for (const t of TEXT) {
    for (const s of [...SCREEN, ...CHROME]) check(`${t} on ${s}`, resolve(t), resolve(s), 4.5);
    for (const s of SCREEN) {
      const frame = resolve('--color-chrome-top');
      const fade = (c) => over(c, FLICKER_OPACITY, frame);
      check(`${t} on ${s}, flickering`, fade(resolve(t)), fade(resolve(s)), 4.5);
    }
  }
  const alpha = Number(tokens.get('--scanline-alpha'));
  if (!(alpha >= 0 && alpha < 1)) {
    throw new Error(`--scanline-alpha is ${tokens.get('--scanline-alpha')}, not an opacity`);
  }
  const shade = (c) => c.map((v) => v * (1 - alpha));
  for (const t of READOUTS) {
    for (const s of READOUT_SURFACES) {
      check(`${t} readout on ${s}, under the scanlines`, shade(resolve(t)), shade(resolve(s)), 3);
    }
  }
  for (const e of EDGES) {
    for (const s of [...SCREEN, ...CHROME]) check(`${e} edge on ${s}`, resolve(e), resolve(s), 3);
  }

  // Rules that set a text colour and a background together.
  let rules = 0;
  for (const [, selector, body] of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
    const color = body.match(/(?:^|[;\s])color\s*:\s*var\((--[\w-]+)\)/);
    const background = body.match(/background(?:-color)?\s*:\s*([^;]+);/);
    if (!color || !background) continue;
    const value = background[1].trim();
    const where = selector.trim().replace(/\s+/g, ' ');
    const solid = value.match(/^var\((--[\w-]+)\)$/);
    const tint = value.match(/^color-mix\(in srgb,\s*var\((--[\w-]+)\)\s+(\d+(?:\.\d+)?)%,\s*transparent\)$/);
    if (solid) {
      check(`${where}: ${color[1]} on ${solid[1]}`, resolve(color[1]), resolve(solid[1]), 4.5);
    } else if (tint) {
      for (const s of SCREEN) {
        const under = over(resolve(tint[1]), Number(tint[2]) / 100, resolve(s));
        check(`${where}: ${color[1]} on ${tint[2]}% ${tint[1]} over ${s}`, resolve(color[1]), under, 4.5);
      }
    } else {
      continue;
    }
    rules += 1;
  }
  if (rules === 0) failures.push('no rule pairs a text colour with a background: the parser has drifted');

  const accent = resolve('--color-accent').join();
  for (const s of STATUS) {
    if (resolve(s).join() === accent) failures.push(`--color-accent is the status colour ${s}`);
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
  `contrast: all ${pairs} pairs clear the floor (text 4.5:1, field edges, focus and large ` +
    'readouts under the scanlines 3:1), plain and flickering; the accent is no status colour.',
);
