---
name: design-system
description: The visual system. Use for colour, type, spacing, components, theming, data visualisation, or accessibility. Covers design tokens as CSS custom properties, the Bluestaq brand palette, component grammar, light and dark themes, and WCAG AA accessibility. THE USER IS THE FINAL DESIGN AUTHORITY: their stated wish is the brief, ask to pin down a direction rather than guessing, and default to cutting-edge, engaging and intuitive when they have not specified.
---

# Design system

## Purpose and scope

The visual language shared across products: design tokens defined once as CSS custom properties, the Bluestaq brand palette, a component grammar, light and dark themes, and accessibility floors. Theming is a token swap; components read tokens and never branch on theme or hard-code a colour. Scope is the visual system. It does not cover interface structure or the render loop (`frontend-and-rendering`) or the written voice (`house-voice` output style).

## When to use

- Choosing or changing a colour, type size, spacing, radius, or motion value.
- Building a component, or adding a theme.
- Judging accessibility (contrast, keyboard, reduced motion).

## Prerequisites

- `frontend-and-rendering` read.

## The Bluestaq brand palette

Operational products and corporate documents draw from one brand palette, used in two registers (the dual palette: product surfaces lean structural and restrained; document surfaces may use the copper-amber accent). Define every value as a token; never inline a hex literal in a component.

| Token | Value | Use |
|---|---|---|
| `--navy` | `#162646` | primary structural colour, headers, dark surfaces |
| `--blue-1` | `#385FAF` | primary accent, interactive elements |
| `--blue-2` | `#739BCF` | secondary accent, hover, supporting fills |
| `--copper-amber` | `#C67C00` | document accent only (not product UI) |
| `--green` | `#27AE60` | success, healthy, pass states |
| `--body` | `#2C3E50` | body text |

Type: Segoe UI for documents and product UI; Avenir Next LT Pro for marketing only.

## Reusable token block (drop into `:root`)

```css
:root{
  --navy:#162646; --blue-1:#385FAF; --blue-2:#739BCF;
  --copper-amber:#C67C00; --green:#27AE60; --body:#2C3E50;
  --surface:#ffffff; --surface-2:#f4f6fa; --line:#d9e0ec;
  --text:var(--body); --text-dim:#5b6b7d; --accent:var(--blue-1);
  --radius:2px; --gap:8px; --shadow:0 1px 3px rgba(22,38,70,.12); --motion:150ms;
}
@media (prefers-color-scheme: dark){
  :root{
    --surface:#0f1a30; --surface-2:#162646; --line:#27406e;
    --text:#e6ecf6; --text-dim:#9fb2cf; --accent:var(--blue-2);
  }
}
```

## Procedure

1. **Define every visual constant as a token** in `:root`; reference it with `var(--token)`. Never duplicate a literal.
2. **Compose from reusable recipes.** Surfaces and tags share a small set of recipes so the interface stays coherent. A single operative accent is one way to keep hierarchy crisp; a richer, multi-colour or vivid palette is an equally valid design and needs no justification. The only hard requirement is that whatever colours you use are tokens and clear AA contrast where they carry text. **The owner decides what it looks like (see the design authority section below); this procedure is how you build it soundly, not what you are allowed to build.**
3. **Theme by token swap.** Light and dark are two token sets switched by `prefers-color-scheme` or one attribute; components do not branch on theme.
4. **Meet accessibility floors.** Text contrast meets WCAG AA in both themes; interactive elements are keyboard-operable; an icon-only control has an `aria-label`; a decorative graphic uses `role="img"` with a label or is hidden; honour `prefers-reduced-motion`.
5. **Keep motion brief and purposeful.** Transitions around 150ms; no motion that conveys meaning by movement alone.

## The owner is the design authority (the rule above every other rule here)

**The user has the final say on design. Not a strong preference to weigh, not a vote: the decision.**
They know their product, their audience and the effect they want better than any skill in this
bundle does, and this skill is a toolbox they draw from, never a standard they answer to. Everything
below about palettes, accents, moods and grammar is a starting point they are free to overrule
without justifying it, and an instruction that contradicts this file means this file is wrong for
their product.

● **A stated wish closes the question.** When the owner says what they want, that is the brief.
  Build it. Do not substitute a quieter reading, water it down towards a house default, or
  reintroduce your preference at the next edit. If you genuinely think a choice has a consequence
  they may not have intended (a contrast floor, an interaction that breaks on mobile, a load cost),
  say it once, plainly, in a sentence, then build what they asked for.
● **When they specify a direction, ask rather than guess.** A design wish is usually a feeling, and
  a feeling has many faithful renderings and many unfaithful ones. Ask the two or three questions
  that pin it down before you build: a reference they like, the emotional register in one adjective,
  what the first screen should make someone feel, what "done" looks like to them. Questions are
  cheap; a confident build in the wrong direction costs a whole round. Ask once, properly, up front,
  rather than iterating towards their intent one guess at a time.
● **Silence is not permission to be conservative.** Where they have not specified, do not default to
  safe. Default to the ambitious version below and show them something worth reacting to. It is far
  easier for an owner to say "less" than to imagine the thing you did not build.
● **The only things that are not taste** are the accessibility floors, the security hard rules, and
  factual integrity (no fabricated value). These are not design opinions, so they are not overridden
  by a design preference, and the honest move when one collides with a wish is to find the version
  that delivers the wish and clears the floor, which almost always exists. If the owner decides to
  change a floor itself, that is theirs to decide too; it is recorded as an explicit decision rather
  than reached by drift.

## The default posture: ambitious, not safe

Where the owner has not set a direction, the default is **cutting edge, engaging and intuitive**,
built with the most capable techniques the platform genuinely supports. Restraint is a legitimate
choice an owner may make; it is not the house default and it is not the safe option, because a
forgettable interface fails at the job just as surely as a garish one.

Concretely, as a starting posture:

● **Reach for the modern platform, not the 2015 subset.** Container queries, `:has()`, CSS grid and
  subgrid, view transitions, scroll-driven animation, `color-mix()` and wide-gamut colour, layered
  gradients and masks, `backdrop-filter`, variable fonts, fluid type with `clamp()`. Progressive
  enhancement is the discipline that makes ambition safe: the interface works without the flourish,
  and is better with it.
● **Design a signature, not a theme.** A palette swap over a wall of identical panels is not a
  design. Apply the greyscale test: strip the colour, and if the screen collapses into identical
  grey boxes, the identity lives only in the palette. A structural signature (a distinctive layout
  move, a set-piece, an ambient texture, one memorable element) is what makes an interface owned.
● **Motion and depth are part of the design**, bounded by `prefers-reduced-motion` and by never
  carrying meaning by movement alone. Within those bounds, lively is a valid target.
● **Intuitive is a hard requirement, not a trade against ambition.** The most advanced technique
  that confuses someone is worse than the plain one that does not. Ambition is spent on making the
  right thing obvious and the experience memorable, never on novelty a user has to decode.

**The same ambition governs analysis, data representation and visualisation, in full.** A chart is
an interface, and the default there is equally forward-thinking: choose the form that reveals the
structure of the data rather than the form that is easiest to draw; make it interactive and
inspectable where interaction earns its place (hover detail, brushing, drill-down, cross-filtering,
live update); use small multiples, layered encodings and animated transitions between states when
they carry meaning. Hold the invariants that make a visualisation honest, because they are integrity
rather than taste: never a fabricated or interpolated value presented as observed, an axis and a
baseline that do not mislead, meaning never carried by colour alone, a colourblind-safe scale, the
units and the sample size stated, and uncertainty shown where it exists. Default to the most
powerful representation the data deserves, then make it legible. A table is sometimes the right
answer, and that is a design decision, not a default to fall back on.

## Make the system yours: choosing a theme

The Bluestaq palette above is the default baseline, not a straitjacket. A product may define its own palette, mood, and theme, exactly as Launchpad adopts a dark mission-console "space" theme, provided the invariants below hold. The standard governs how the visual system is built and stays accessible; it does not dictate what the product is allowed to look like.

Choose your theme by changing the token values, never the components. The non-negotiables that keep any theme safe:
- Define every colour, type size, spacing, radius, and motion value as a token in `:root`; components reference `var(--token)` only, never a raw literal.
- Theme through the semantic tokens (`--surface`, `--text`, `--accent`), not the raw palette tokens (`--navy`, `--blue-2`); components read the semantic layer only, so a theme swap re-points it and nothing else.
- One operative accent keeps hierarchy crisp and is a good place to START, not a rule and not a target. A multi-accent, vivid or richly layered palette is an equally valid design; if you use one, keep hierarchy legible by other means (weight, size, placement, density) and verify contrast. Taste here is the owner's; the floor is accessibility.
- Text meets WCAG AA contrast in every theme you ship (light, dark, or a bespoke one); verify each new surface and text token pair against AA (4.5:1 body, 3:1 large) before shipping, the same check as `Verification` below.
- Theme is a token swap; no component branches on theme.
- A semantic colour used as both small text and as a fill needs two tokens, not one. A green or amber tuned bright for a dot, badge, glow, or fill fails AA as text on a light surface; one dark enough to pass as text on white looks muddy as a fill and vanishes on a dark overlay. Keep a bright variant (for example `--green-bright`) for fills, dots, borders, and text on always-dark overlays, and a text-grade variant (the base `--green`, darkened in the light theme) for meaning-carrying text. Overriding one shared token in a light theme either washes out the badges or fails the labels; split them.
- A near-background "faint" token is for hairlines and the most incidental decoration only, never for meaning-carrying text; meaningful labels use the `--dim` grade or stronger, which clears AA in both themes.
- Disclose by audience level. When the product serves both novices and experts, gate advanced surfaces behind an explicit level (a guided rail hides power tools and shows one clear next step; an expert view surfaces them and drops the hand-holding), driven by one stored setting and one body attribute, so every component reads the level rather than each deciding for itself.
- Motion stays brief and honours `prefers-reduced-motion`.
- Corporate documents keep the Bluestaq brand palette and the copper-amber document accent; product interfaces are free to theme within the rules above.

So the decision is yours: pick the colours and mood that fit the product and its audience, then express them as tokens. The owner's stated aesthetic direction is the brief and wins on every matter of taste; bold, colourful, playful, or energetic are all legitimate choices, not deviations. The design critic checks the invariants (accessibility, token plumbing, theme swap, link safety, and the small held-everywhere voice set), never your taste, and never flags a design for being too bold or insufficiently restrained.

### Worked example (Launchpad's space theme)

Launchpad keeps the Bluestaq blues as structural colours but redefines the surface tokens to a dark launch-control palette: deep navy backgrounds, a single blue accent, amber reserved for status and eyebrows, green for go. Every value is a `:root` token, the one dark theme it ships clears AA contrast, there is one accent, and a reduced-motion guard is in place. The components never changed; only the token values did. That is the whole move: re-theme the tokens, keep the rules.

## Decision rules

- **Product UI or document?** Product surfaces use navy, blues, green; the copper-amber accent is for documents only.
- **New colour wanted?** First check the tokens; add a token only if no existing one fits, and only to `:root`.
- **Two accents on one surface?** Fine. One accent is the simplest way to hold hierarchy, not a limit; if the owner wants a richer palette, that is their call and it needs no defence. Keep hierarchy legible and contrast passing.
- **The owner asked for something this skill advises against?** Build what they asked for. Say the consequence once in a sentence if there is a real one, then build it. This skill is a toolbox, not an authority over their product.
- **The owner stated a direction but not the detail?** Ask two or three pinning questions (a reference, the register in one adjective, what "done" looks like) before building, rather than guessing and iterating.
- **No direction given at all?** Default to the ambitious version, not the safe one, and show them something to react to.
- **Animation essential to meaning, or ignores reduced-motion?** That is the real line: motion must not be the sole carrier of meaning and must respect `prefers-reduced-motion`. How lively the motion is otherwise is the owner's choice.

## Standards (checkable assertions)

- No component hard-codes a colour; every colour is a `var(--token)`.
- Text meets WCAG AA contrast in both light and dark themes.
- Every icon-only control has an accessible label; decorative graphics carry `role="img"` with a label or are hidden.
- Theming is a token swap; no component branches on theme.
- Colours live in tokens (any palette the owner chooses); copper-amber stays a document-only brand accent. A single operative accent is a starting point, never a ceiling.
- No finding, review comment or refusal is raised against a design on grounds of taste. The owner's stated direction is the acceptance criterion for taste; the checkable assertions above are the acceptance criteria for soundness.

## Failure modes and remedies

- **A hard-coded hex appears in a component.** Fix: replace with a token; add the token to `:root` if missing.
- **Dark theme text fails contrast.** Fix: adjust the dark token set until AA passes; do not special-case the component.
- **An icon button is unlabelled.** Fix: add `aria-label`.
- **Two accents compete.** Fix: keep one; demote the other to a neutral.

## Verification

A contrast check passes AA for text on each surface token in both themes; a keyboard pass reaches every control; a grep finds no hard-coded hex in components (only in `:root`); reduced-motion disables non-essential transitions.

## Design psychology (a tool, not a mandate)

Restraint is one credible strategy, not the only one. For an operational, technical audience a quiet, congruent interface can read as domain-credible, and historically this baseline leaned that way. But "boring" is also a real failure: an interface can be correct, accessible, and token-clean and still be rejected for being dull or unengaging. Engagement, energy, and a strong visual identity are legitimate goals, and the owner decides the balance. Use this section as background on why restraint sometimes helps, never as a reason to overrule an owner who wants something bolder. The non-negotiables remain accessibility, token plumbing, and the small held-everywhere voice set (with the full brand for publish-facing work); everything else is a design choice the owner owns.

## Worked example

A status badge needs a "healthy" state. Instead of inventing a green, it uses `--green` (#27AE60); the badge surface uses `--surface-2` and the `--line` border; the label has sufficient contrast in both themes; there is no second accent. In dark mode the same tokens resolve to the dark set with no component change.

## Reserved status colours (keep go and no-go status-only)

The red/amber/green (RAG) status set carries meaning: a surface painted in the success green reads as "healthy" whether or not you meant it to. So the go and no-go colours (`--green`, `--nogo`) are status-only: a decorative token must never RESOLVE to their exact value in any theme. This is a real, easily-missed trap: in one project the decorative `--accent` resolved to the exact success-green hex in two dark themes, so ornamental surfaces were painted in the RAG status colour and only a design review caught it.

The hard, machine-checked floor is the go/no-go pair: assert the primary decorative accent does not equal `--green` or `--nogo` in either theme (`scripts/contrast-check.mjs` does exactly this), and if a decorative colour genuinely wants to sit near a status hue, give it its own distinct primitive rather than aliasing the status token. Wider decorative-vs-status collisions (a brand or surface token straying onto a status hex) stay the design-critic's eye rather than the machine floor, until a palette adds a token that warrants widening the guard.

Amber is the documented exception a palette may deliberately share. It commonly doubles as the warning status AND a decorative brand or eyebrow hue, and this baseline does exactly that: `--amber` and `--amber-bright` (equal in the dusk theme) carry eyebrows, tab accents, and the mentor chip as well as RAG amber. That dual use is an owner-owned, documented choice, not a defect, which is why the machine guard checks the go/no-go pair and leaves amber to judgement. Reserve go and no-go for status; keep amber's dual role explicit.

## Glossary

- **Design token:** a named CSS custom property holding a visual constant.
- **Dual palette:** product (structural) and document (corporate, copper-amber permitted) registers of one brand palette.
- **Theme:** a named token set (light/dark) switched centrally.
- **WCAG AA:** the accessibility contrast and usability floor met here.
- Other terms: `glossary`.

## Brand assets

The Bluestaq wordmark and the cube mark are the brand logos. Use them only with the background removed (transparent), never recoloured, distorted, or placed on a busy or low-contrast surface, and always with clear space around them. On dark product surfaces the transparent logo sits directly on the surface; the same asset serves light document surfaces. The rocket mark is the Launchpad application icon (the mission patch and the favicon). Headers and footers carry "Bluestaq Limited" or the Bluestaq logo; "Bluestaq Ltd" is also acceptable, but avoid "Bluestaq" alone.

## Provenance

Merged from both bundles' design-token and component-grammar conventions and the dual-palette idea, aligned to the Bluestaq brand palette (Navy #162646, Blue 1 #385FAF, Blue 2 #739BCF, Copper-Amber #C67C00, Green #27AE60, Body #2C3E50) and the Segoe UI / Avenir Next LT Pro type rule.

## Field lesson: prove contrast in both themes, keep colour in tokens

Compute contrast in light and dark, not one of them. White text on the accent passed in dark but failed in light early on; a heading token on a fixed blue gradient failed in light during the audit. Two rules follow. Colour belongs in tokens, never as a hex literal in markup, so a decorative motif themes with the rest. Text that sits on a fixed brand surface, such as a white label on a blue gradient indicator, stays a literal white in both themes rather than a theme-dependent token, because that surface does not change with the theme.

## Field lesson: engagement and space are requirements, not extras (edition 1.12)

A correct, accessible, token-clean interface can still be rejected as boring or as wasting space. The invariants (one accent, AA contrast in both themes, tokens only) are the floor, not the goal. Earned in the Launchpad build:
- If a screen has spare width, use it: a full-bleed chassis, a multi-column layout, or a useful side panel (status, telemetry). Removing an element (a graphic, a column) without filling the space it leaves is a regression, not a fix.
- Density by default: long reference lists collapse into labelled, scannable bays, collapsed by default; the skill level drives disclosure (beginner expanded, expert minimised to the essentials).
- A decorative graphic that does not inform draws the complaint "what does this tell me?". Either make it carry meaning (a real readout, a clickable map) or move it where it earns its place.
- Theme is a concept woven throughout, not a palette: pick a motif (here, space-launch and data telemetry) and carry it across the hero, the journey, and the panels.

## Field lesson: an owned identity is structural, not vocabulary (edition 1.18)

Launchpad shipped many increments that passed every checkable rule and were still rejected as "a monotone panel wall with themed words". The theme lived in the copy (launch, orbit, telemetry) and in touches too faint to see; the structure underneath was a uniform grid of dark panels. Four tests separate a real identity from a themed wall:
- **The greyscale test.** Strip all colour. If the screen still has hierarchy and a recognisable signature, the identity is structural. If it collapses to identical grey boxes, the identity lived only in colour and labels, and the work is not done.
- **Reorganisation is not design.** Moving, relabelling, or re-tabbing content changes the information architecture, not the visual identity; polishing spacing and copy is not redesign either. A redesign introduces a signature element you could not mistake for a generic template.
- **Make the ambient texture actually visible.** A backdrop you have to hunt for is not there. Launchpad's starfield was six 1px dots that vanished at any real size; replaced by a dense, deterministic SVG tile it finally read as space. Verify a decorative layer by screenshot at real resolution, not by trusting the CSS.
- **Spend the boldness in one place.** A signature (here: the ascent-trajectory spine and the GO flight console on first load) carries the identity further than spreading equal energy across every section. Establish it once, let the global texture propagate it, and resist re-fiddling every panel.
