# Multiple color schemes and dark mode

Use this when a project ships more than one color scheme, asks for dark mode,
or must follow an operating-system preference. A second scheme is another
rendered state of the design, not a mechanical filter.

## Decide from the project

Dark, light, high-contrast, seasonal, user-selected, and single-scheme systems
can all be appropriate. Decide from audience, use duration, environment,
brand, content, platform convention, accessibility, maintenance, and owner
preference. Do not assume that a particular vertical needs or does not need
dark mode.

Record whether the scheme is:

- the primary art direction;
- a system-preference adaptation;
- a manual user choice;
- an accessibility mode;
- a future or explicitly excluded feature.

Do not leave a partial theme that styles only the page background and text.

## Derive relationships rather than invert values

Review every semantic role in each scheme: grounds, surfaces, inks, graphics,
links, focus, selection, disabled, warning, error, success, overlays, media
scrims, fields, charts, maps, code, SVG, canvas, and native controls.

Pure black, pure white, saturated accents, unchanged brand colors, shadows,
lighter elevated surfaces, borders, and glows are all available. Judge them
from rendered contrast, halation, hierarchy, brand fit, and composition. No
color value or elevation method is globally forbidden.

Typography may need optical changes between schemes, but do not require a
weight or spacing adjustment without observing the real face and background.

## Treat media and identity explicitly

Inspect photographs, illustrations, diagrams, logos, transparent assets,
embedded maps, charts, and third-party widgets in every scheme they can enter.
Use approved scheme-specific assets or framing where needed. Do not recolor a
brand mark or invert imagery without authority.

Record material per-scheme behavior in the asset manifest when the project
needs durable handoff evidence.

## Define the preference contract

Choose system following, a binary control, a three-state control, per-page
choice, or no manual control from the product contract. A three-state system
is useful when users need system, light, and dark separately, but it is not a
universal requirement.

When a manual choice exists:

- expose a semantic, keyboard-operable control with a clear current state;
- persist only what the product and privacy contract permit;
- apply the choice early enough to avoid a disruptive flash;
- update `color-scheme` and relevant native or embedded content;
- define what happens when the system preference changes.

## Verify each scheme as a real state

Capture and inspect every materially different scheme at the project-relevant
wide and narrow conditions, plus states whose colors or assets differ. Check:

- rendered-pixel contrast for solid, translucent, image, and gradient grounds;
- focus, selection, hover, disabled, error, empty, loading, and success;
- live switching, first paint, persistence, browser chrome, canvas, charts,
  maps, and embeds;
- media edges, logos, icons, illustrations, and baked-in backgrounds;
- forced colors as its own rendering mode rather than a synonym for dark;
- performance and duplicate asset cost.

Do not call the secondary scheme complete because token arithmetic or the
primary scheme passed.
