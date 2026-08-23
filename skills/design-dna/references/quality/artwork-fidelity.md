# Supplied-artwork fidelity

Use this when the client or owner supplies the visual answer itself: a
mockup, a Figma export, a screenshot of a design, a printed piece to
translate, an existing page to match, or any artwork the build must
reproduce rather than reinterpret. The job changes at that moment. The
direction already exists and belongs to someone else; invention is no
longer the work, and the skill's direction machinery (taste calibration,
Project Contrast, Direction Challenge) stands down for the covered surface
except where the artwork is silent.

The governing standard, in one sentence: **the goal is not a build inspired
by the artwork; the goal is a build visually faithful to the artwork,
translated into a real, working, accessible page.** Faithful means the
rendered result reads as the same design, not that every pixel is cloned;
spacing logic, type relationships, and component families matter more than
pixel identity.

## Contents

- [Declare the mode and its boundary](#declare-the-mode-and-its-boundary)
- [Read the artwork as a specification](#read-the-artwork-as-a-specification)
- [Extract before building](#extract-before-building)
- [Resolve ambiguity up the ladder](#resolve-ambiguity-up-the-ladder)
- [Hold the line against drift](#hold-the-line-against-drift)
- [Reconcile fidelity with the floors](#reconcile-fidelity-with-the-floors)
- [Prove fidelity in the render](#prove-fidelity-in-the-render)

## Declare the mode and its boundary

Record in the project state that supplied-artwork fidelity governs, with
the exact source files, their provenance, and their authority (client
brand, client-approved designer, owner sketch). State what the artwork
covers and what it is silent about: usually it shows one or two widths,
no hover or focus states, no error or empty states, no motion, and a
subset of routes. The silent zones are designed *in the artwork's
language* under this reference; they are not license to reopen the
direction.

Supplied artwork is an authority-tier input: it outranks the producer's
taste and every advisory reference, and is outranked only by truth,
rights, law, accessibility, and working behavior. A conflict with those
floors is surfaced to the owner, not silently resolved in either
direction.

## Read the artwork as a specification

Treat the image the way a printer treats artwork: as the contract.
Inspect it at full size and extract, where visible:

- exact wording of headings, actions, navigation, and labels; the visible
  text is part of the design;
- the type system: families or their closest identifiable posture, the
  scale relationships between roles, weight and case usage, alignment
  logic, line counts and wrapping behavior at the shown width;
- the spatial system: section rhythm, internal padding, gutters, the
  distances between heading, support text, and action; card dimensions
  and their cadence;
- the component family: control shapes, radius logic, borders and
  dividers, fills against outlines, shadow behavior, iconography;
- the color system: grounds, inks, accents, and where each is permitted
  to appear;
- media treatment: crops, aspect ratios, framing devices, grade;
- the repeated motifs that make the design itself.

Measure rather than eyeball wherever the source permits: sample colors
from the file, measure gaps and type sizes in the bitmap, and derive the
ratios. The goal is not pixel arithmetic for its own sake; it is faithful
spacing and scale logic, captured as numbers so the build can be checked
against them. Record the extraction as a token sheet in the project state
before the first component is built. Judging relationships from a small
crop distorts them; measure against the full composition.

## Extract before building

Do not begin implementation from memory of the artwork. The common failure
is reading the image once, holding an impression, and building the
impression: the result is a generic page wearing the artwork's palette.
The extraction sheet is the bridge; implementation consumes the sheet, and
disagreements between the sheet and the artwork are resolved by looking
again, not by preference.

When several comps are supplied (multiple routes, or wide and narrow of
the same route), extract each and reconcile the system across them. Where
the comps disagree with each other in a way that changes the build, flag
the inconsistency to the client as a question rather than silently
normalizing to one side; the difference may be intentional.

## Resolve ambiguity up the ladder

Where the artwork is unreadable, missing a state, or silent, resolve in
this order, recording each decision:

1. preserve the visible design language: the answer that the artwork's
   own system implies;
2. preserve the layout and spacing logic already extracted;
3. preserve the component family: an unshown control takes the shown
   family's form;
4. preserve the mood and finish level;
5. when a region is genuinely unreadable or a needed asset is flattened
   into the image, request the source: the original file, a higher-
   resolution export, the font names, the hex values, the icon set. An
   unreadable specification region is a legitimate blocker, and asking
   beats guessing;
6. only after those, choose the most implementation-friendly faithful
   reading, and record it as an interpretation the owner can veto.

Do not fill ambiguity with generic defaults, and do not use a silent zone
to reintroduce the producer's own taste.

## Hold the line against drift

Design drift is the mode's characteristic failure: the artwork is strong,
the extraction is honest, and the coded result still slides toward the
generic because implementation convenience made a hundred small
substitutions. During implementation do not:

- simplify a distinctive section into a familiar template row;
- compress the artwork's generous spacing into default rhythm;
- flatten its type relationships into a stock hierarchy;
- swap its component shapes for a library's defaults;
- merge distinct section structures into one repeating pattern the
  artwork does not have;
- redesign anything because a faithful build is more work.

The finished build must still read as the same design as the supplied
artwork. When a faithful reading is technically impossible or harmful
(the reconciliation cases below), the deviation is recorded and shown,
never slipped in.

## Reconcile fidelity with the floors

Fidelity never waives the assurance boundaries. When the artwork itself
violates a floor, the resolution is explicit:

- **contrast and access:** a supplied combination that fails required
  contrast, target size, or focus visibility is built as close to the
  artwork as the floor allows, and the exact deviation is reported to the
  owner with the reason; both the artwork's value and the shipped value
  are recorded;
- **truth:** proof-shaped content in the artwork (counts, testimonials,
  logos) follows the same truth rules as any content; the client supplies
  the real facts or the treatment ships with honest stand-ins per the
  placeholder register;
- **behavior:** the artwork's controls must actually work; a drawn
  control with no reachable behavior is implemented, honestly disabled,
  or raised as a question;
- **responsiveness:** widths the artwork does not show are composed from
  its extracted system under the responsive reference, as the same design
  under pressure, not as a second design.

## Prove fidelity in the render

Fidelity is a rendered claim and is proven the way the skill proves
everything: by looking, with the comparison bound to exact artifacts.

- Capture the built result at the artwork's own width and place it beside
  the artwork; use the [rendered comparison](render-comparison.md)
  discipline with the supplied artwork as the baseline.
- Walk the extraction sheet against the render: type roles, spacing
  cadence, component shapes, color placement, media treatment. Each row
  is confirmed, deviated-with-reason, or defected.
- Review the whole at arm's length after the row-by-row pass: does the
  build read as the same design? A page can pass every row and still have
  drifted in aggregate; the gestalt judgment is part of the proof.
- Record remaining deviations in the handoff with their reasons, so the
  owner approves the differences knowingly.

The preship gate applies in full; fidelity adds the comparison evidence,
it does not replace the floors, the launch-completeness record, or the
engineering review.
