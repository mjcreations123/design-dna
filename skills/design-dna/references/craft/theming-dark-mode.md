# Dual themes and dark mode

Use this when a project ships more than one colour scheme, when a client asks
for dark mode, or when a surface must survive the operating system flipping
it. [Colour and composition](color-composition.md) owns the palette itself
and the ink-versus-graphics split; [systems and
components](systems-components.md) owns token architecture. This file owns
the decision to ship a second scheme and the craft of making both of them
real.

Dark mode is a second design, not a filter over the first. Shipping it
doubles the surface that has to be art-directed, contrast-tested, and
screenshotted, and half-finished dark mode is worse than none.

## Contents

- [Decide whether to ship it](#decide-whether-to-ship-it)
- [Derive the dark scheme, never invert it](#derive-the-dark-scheme-never-invert-it)
- [What has to change besides the background](#what-has-to-change-besides-the-background)
- [Imagery, logos, and media](#imagery-logos-and-media)
- [The preference contract](#the-preference-contract)
- [Verify both schemes independently](#verify-both-schemes-independently)

## Decide whether to ship it

Ship a second scheme when the project earns it: long reading sessions, a
tool used at night, a client whose brand genuinely lives dark, an operating
context where the surrounding UI is dark. Skip it when the site is a short
Persuade surface whose palette is derived from the client's world and whose
visitors arrive once; a bakery does not need dark mode, and the effort buys
more elsewhere.

Never let dark-by-default arrive by inertia. A dark page with a saturated
accent glow is a named cluster in the
[generator defaults](../convergence-watch.md#dated-watch-the-generator-defaults):
permanent dark mode with mid-grey body text is what a model reaches for when
nothing told it what the palette should be. Dark is a legitimate committed
direction, and the test is whether the project's own evidence chose it. When
it did, record that in the direction; when it did not, the light scheme is
the design and dark is a feature with a cost.

If the answer is "not now," say so in the direction record rather than
leaving a broken half-theme in the tokens. A `prefers-color-scheme` block
that styles four things and misses the rest is a defect, not a start.

## Derive the dark scheme, never invert it

An inverted palette is not a dark palette. Derive it:

- **Do not use pure black.** A near-black in the project's own hue family
  (a warm brown-black for a bakery, a cool slate for a marine subject) holds
  the direction; #000 flattens it and raises halation against light text.
- **Do not use pure white for body text.** Full-strength white on near-black
  vibrates at reading sizes. Step it down and let the hierarchy come from
  weight and spacing as well as luminance.
- **Saturated colours read brighter on dark.** A brand accent tuned for a
  white page usually needs desaturating and lightening to sit calmly on a
  dark one. The
  [ink versus graphic split](color-composition.md) applies per scheme: an ink
  that clears 4.5:1 on paper may fail on the dark ground and needs its own
  purpose-built variant.
- **Elevation inverts its logic.** On light, higher surfaces cast shadows; on
  dark, shadows disappear into the background and higher surfaces are
  expressed by getting lighter. Copying the light scheme's shadow stack into
  dark produces flat, muddy cards.
- **Borders and dividers need separate values.** A hairline that reads as a
  quiet rule on paper often vanishes on dark or, over-corrected, glows.

## What has to change besides the background

Audit every token role, not only surface and text: focus rings, selection,
disabled states, error and success colours, scrim and overlay opacity, code
syntax highlighting, chart and data-visualisation series per
[data visualization](data-visualization.md), map tiles, form field fills, and
any colour baked into an SVG or an inline style.

Type may need a small optical adjustment. Light text on a dark ground gains
apparent weight, so a face set at a given weight on paper can read heavier in
dark; a variable font makes this cheap to correct, and the
[typography numbers](typography.md#the-numbers) still bound the result.

## Imagery, logos, and media

Photographs generally survive both schemes, but their surrounds do not: a
photo with a white studio background sits in a glowing rectangle on a dark
page. Decide per asset whether it is cropped, given a transparent
background, given a scheme-specific variant, or deliberately framed.

Logos and marks almost always need a second version. A dark-ink logo on a
dark ground is the most common visible break, and recolouring a client's mark
without permission is a brand decision, not a CSS one; see
[brand systems](brand-systems.md). Never apply a blanket CSS filter to invert
imagery, which mangles photographs and shifts brand colour.

Illustrations, diagrams, and any asset with baked-in white need explicit
treatment. Register each one in the
[asset manifest](../../templates/asset-manifest.yml) with its per-scheme
behaviour rather than discovering the problem in review.

## The preference contract

Respect the operating system by default through `prefers-color-scheme`. When
the product also offers a manual control, the contract has three states, not
two: system, light, and dark. A two-state toggle silently overrides the
system preference forever after one tap, which is a bug people notice at
dusk.

Persist an explicit choice, apply it before first paint so the page does not
flash the wrong scheme, and keep the control's current state legible without
relying on the icon alone. Announce it as a real control with an accessible
name, not a decorative sun and moon.

`color-scheme` on the root lets form controls, scrollbars, and other native
chrome follow the theme; without it, a dark page keeps light native widgets.

## Verify both schemes independently

Both schemes are separate deliverables under
[ABSOLUTE 11](../../policy/absolutes.md): the screenshot pair is required at
~1440 and ~375 in each scheme, saved and looked at, not assumed from the
light run.

- Re-measure contrast in dark from rendered pixels, per the
  [render harness](../quality/render-harness.md). Token arithmetic does not
  see a scrim, a photo, or a gradient behind the glyphs, and a value that
  passes on paper commonly fails on dark.
- Check focus visibility in both; a focus ring tuned for a white page often
  disappears on a dark one.
- Test the flip while the page is open, not only on load, including any
  canvas, chart, embedded map, or iframe that caches its own colours.
- Test forced-colors mode separately. It is a third rendering, not dark mode,
  and it overrides both schemes.
- Check every state in both: hover, disabled, error, empty, loading, and any
  surface that only appears after interaction.
