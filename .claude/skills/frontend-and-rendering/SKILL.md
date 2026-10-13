---
name: frontend-and-rendering
description: The interface layer. Use for UI structure, rendering, or the interactive canvas. Covers the static inline HTML/CSS/SVG single file and from-scratch vector renderer with culling and level-of-detail, the server served-static single-page app, offline-first fallback, escaping every untrusted value, icon and manifest head wiring, and instant-close panels with deferred heavy paint.
---

# Frontend and rendering

## Purpose and scope

The presentation layer for both archetypes. The static artifact is inline HTML, CSS, and SVG in one file, with a from-scratch projected vector renderer (culling, level-of-detail, integer-pixel paths). The server app serves a static single-page app (SPA) from `public/`, offline-first against a baked seed. Both escape every untrusted value at render, wire icons and a web manifest, and make panels close instantly with heavy paint deferred. Scope is structure and the render loop; visual tokens are in `design-system`, scheduling in `state-management`, data shape in `data-layer`.

## When to use

- Building or changing UI chrome, panels, or overlays.
- Touching the interactive canvas or renderer, or its performance.
- Adding any place that renders untrusted data into the document.

## Prerequisites

- `code-architecture`, `state-management`, `data-layer` read.

## Procedure (both archetypes: safe rendering)

1. **Escape every untrusted value at render**, in both text and attribute contexts, and restrict links to an allow-list of schemes.
   ```js
   function attr(s){ return String(s||"").replace(/&/g,"&amp;").replace(/"/g,"&quot;")
     .replace(/'/g,"&#39;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
   function safeUrl(u){ u=String(u||"").trim(); return /^(https?:|mailto:)/i.test(u)?u:""; }
   ```
2. **Make panels close instantly; defer heavy paint.** A drawer or modal becomes interactive the moment it opens; heavy rendering (canvas, chart) is deferred behind a double `requestAnimationFrame`, and the deferred draw aborts if the panel was already closed. Close on the control, the scrim, and Escape.
3. **Wire icons and the web manifest in the head.** A favicon (inline data URI for offline plus a `/favicon.ico`), an apple-touch icon, and a `site.webmanifest` with 192 and 512 icons and a theme colour. One square source image feeds them all.

## Procedure (static: from-scratch vector renderer)

1. **Project each point** with the forward projection; mark visibility (back-face).
2. **Cull whole objects behind the limb** using a precomputed centroid and angular radius (`data-layer` derived fields) before any vertex work.
3. **Build paths with level-of-detail and integer rounding.** Stride vertices during interaction; round to whole pixels; break the path when a run goes behind the limb.
4. **Write the frame once** (`element.innerHTML = built`), scheduled via `frameSoon` (`state-management`).

## Procedure (server: served-static SPA)

1. **Keep the interface a served static file.** The backend serves `public/` directly; no bundler. A single `public/index.html` is acceptable only when single-file portability is a real requirement (it forces an `unsafe-inline` Content Security Policy); otherwise split assets so the policy can drop `unsafe-inline`. State which you chose.
2. **Be offline-first.** Prefer the live API dataset; if the backend is unreachable, fall back to a baked seed so the page still works. Wrap every fetch so a failure degrades to local data and never throws to the top level.
3. **Split logic from wiring so the logic is coverable.** Put the pure parts (parsers, formatters, validators, state derivations, string and data builders) in their own importable modules and keep the browser file to event binding, element lookups, and paint. The unit runner then covers the logic directly. This is not tidiness: the App Store's coverage check counts any file absent from the coverage report at 0%, so a growing no-exports client script silently drags the metric under the floor whatever the server's coverage is, and no `sonar.sources` or exclusion setting will hide it (`appstore-gate-compliance` section 2.1, `code-architecture`).

## Decision rules

- **Renders per frame?** Then it must cull and use level-of-detail (static renderer). Static chrome does not.
- **Single file vs split (server)?** One file only when shipping a single openable file is a real requirement; otherwise split so the CSP can drop `unsafe-inline`.
- **Render path?** Any value originating outside the code (user input, API or model data) goes through the escaper. When in doubt, escape.
- **Defer or not?** Defer any synchronous render over a few milliseconds behind double rAF so panel open and close are never blocked.
- **Adding a browser handler with real logic in it?** Extract the logic into an importable module and unit-test it in the same change; leave only the binding in the browser file. Every new or changed executable line in a release is scored by the platform's coverage-on-new-code check, so an untested new handler fails the gate even when the rest of the tree is green.
- **Performance budget (static)?** If a full-detail frame exceeds budget, raise the simplification tolerance in `data-layer`; never remove culling.
- **A design or interaction question?** The user decides, and this skill does not get a vote on taste. Build what they asked for; ask to pin down a stated direction rather than guessing; where nothing is specified, default to the ambitious version rather than the safe one (`design-system`, the design authority section).
- **Rendering data (a chart, a dashboard, an analysis view)?** It is an interface and gets the same ambition: choose the form that reveals the structure of the data, make it inspectable where interaction earns its place, and prefer a live, interactive representation over a static picture of one. The invariants are integrity, not taste: never a fabricated or interpolated value shown as observed, an axis and baseline that do not mislead, never meaning by colour alone, a colourblind-safe scale, units and sample size stated, uncertainty shown where it exists (`design-system`).

## Standards (checkable assertions)

- Every untrusted value is escaped at render; links are restricted to http, https, and mailto.
- A panel closes instantly via control, scrim, and Escape; heavy paint is deferred and aborts if closed.
- The head wires a favicon, apple-touch icon, and a web manifest from one source image.
- Static: every per-frame ring goes through culling and level-of-detail; projected coordinates are integer-rounded; one `innerHTML` write per frame.
- Server: the interface runs offline against a baked seed when the backend is unreachable (no top-level throw on a failed fetch).
- The client's pure logic sits in importable modules covered by the unit runner; the browser-only file carries wiring and paint, and appears in the coverage report or is knowingly accounted for.

## Failure modes and remedies

- **A value renders unescaped and breaks markup or injects script.** Fix: route it through `attr`/`safeUrl`; add the escape at source.
- **A `javascript:` link slips through.** Fix: `safeUrl` allows only http, https, mailto.
- **The drawer is sluggish to close.** Fix: heavy paint is on the close path; defer behind double rAF and abort when closed.
- **The page errors when offline (server).** Fix: a fetch throws to the top level; wrap it and fall back to the seed.
- **Geometry smears across the globe (static).** Fix: break the path on back-face (`!vis`).

## Verification

Static: the headless render-check screenshots desktop and mobile, confirms crisp edges, no smearing, smooth drag, and a clean console. Server: `npm run test:e2e` loads the page, renders every view asserting zero page errors, and opens and closes a panel.

## Worked example

Server: a list renders records whose names contain apostrophes and ampersands. Each name goes through `attr`, so markup stays intact and no script is injected. The drawer opens instantly; its canvas draws one frame later and aborts if closed immediately. With the backend stopped, reloading shows the baked seed. The Playwright smoke test passes with zero page errors.

## Glossary

- **SPA:** Single-Page Application.
- **Escaping:** converting markup-significant characters to safe entities before insertion.
- **Offline-first:** prefer the live API, fall back to a baked seed.
- **Deferred paint:** delaying heavy synchronous render behind a double rAF.
- **Back-face cull / level-of-detail:** skipping far-side geometry; decimating vertices during interaction.
- Other terms: `glossary`.

## Provenance

Merged from the static artifact's orthographic renderer (projection, cull, level-of-detail, integer rounding) and the server bundle's frontend skill (served-static SPA, offline-first, escaper and safeUrl, drawer instant-close with deferred paint, icon and manifest wiring).

## Field lesson: overlays must be siblings of the inerted background

When a modal, command palette or toast makes the rest of the page inert (the `inert` attribute or `aria-hidden`), the overlay must be a sibling of the inerted region, never a child of it. If the overlay lives inside the element you inert, its own controls inherit `inert` and stop responding: clicks land on the backdrop, and an automated check reports the body intercepting pointer events with the target "not stable". Keep the splash, the command palette and similar overlays outside `<main>`, then inert `<main>` and the surrounding chrome.
