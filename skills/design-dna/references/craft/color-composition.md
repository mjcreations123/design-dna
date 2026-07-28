# Color and composition

Use this when defining or materially changing the palette, visual hierarchy, or page composition.

## Derive roles before values

Start with project evidence: existing brand color, product material, photography, environment, data semantics, or accessibility needs. Define roles such as:

- canvas, surface, raised surface, border, and overlay;
- primary text, secondary text, muted text, and inverse text;
- action, focus, selection, link, and visited link;
- success, warning, danger, information, and neutral status;
- expressive accent and data-series colors.

Do not create local colors for every component. Let components consume named roles. Do not use color alone to communicate status or action.

## Build tonal hierarchy

- Separate surfaces only when the distinction carries hierarchy or state.
- Make primary content legible before adding accent.
- Reserve the strongest contrast for the most important information or action.
- Test foregrounds over every surface and image on which they appear.
- Verify hover, active, disabled, selected, focus, error, and visited states.
- In dark themes, design elevation and contrast deliberately; do not merely invert values.

A monochrome, restrained, saturated, or multicolor palette can all be correct. Judge the system, not the ingredient.

When perceptual color spaces or wide-gamut color materially improve the system,
define an sRGB fallback first, place the enhanced value behind support and gamut
conditions, and verify the rendered result on both ordinary and wide-gamut
displays. OKLCH and Display-P3 are implementation tools, not marks of quality;
check clipping, interpolation, contrast, screenshots, and forced colors.

## Compose from the task

1. Establish the primary scan path.
2. Place the most consequential information where the user encounters the decision.
3. Group by meaning before styling containers.
4. Use alignment to show relationships; break alignment only to create a meaningful focal event.
5. Balance visual mass, not just bounding boxes.
6. Check the composition with real copy, realistic imagery, and actual controls.

Optical alignment may require small corrections for curved letters, icons, image subjects, or asymmetric shapes. Record intentional exceptions as tokens or component rules instead of scattering magic numbers.

## Avoid mechanical composition

Review for:

- identical card grids repeated across unrelated sections;
- every block centered or every section using the same padding;
- boxes nested inside boxes without an information relationship;
- decorative stripes, glows, or surface changes repeated as filler;
- contrast that creates noise instead of hierarchy;
- a palette copied from the framework or reference without project rationale.

These are diagnostic prompts, not bans. A repeated grid or centered layout is valid when content structure and task support it.

## Verify

Test the palette and composition in:

- the most common route and the densest route;
- narrow, intermediate, and wide widths;
- light/dark themes when supplied;
- forced-colors or high-contrast conditions when applicable;
- grayscale or a color-vision simulation as supporting evidence;
- focus, error, selection, disabled, and loading states.

Record actual contrast measurements for required text and UI boundaries. Do not substitute a palette screenshot for rendered-state checks.
