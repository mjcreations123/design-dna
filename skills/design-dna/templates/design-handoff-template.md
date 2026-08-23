# DESIGN.md handoff record

Copy this template to `DESIGN.md` in the project repository when the site
is handed off, and fill it from the project's own accepted system. It is a
client-facing deliverable, not internal evidence: after the repository
transfers, the owner's future developers and AI assistants will edit the
site, and this file is what keeps those edits on-system instead of
drifting toward generic defaults. Write it from the accepted build's real
tokens and decisions; never from another brand's record, and never with
values the rendered site does not actually use.

Delete the guidance sentences in brackets when filling it in. Keep the
file honest as the site evolves: a stale DESIGN.md misleads the next
editor exactly the way stale documentation misleads the next developer.

---

# <Project name> design system

This file describes the design system this site actually ships. When
editing or extending the site, derive new work from these decisions. If a
change deliberately departs from them, update this file in the same
change.

## Contents

- [Voice](#voice)
- [Color](#color)
- [Typography](#typography)
- [Space and shape](#space-and-shape)
- [Components](#components)
- [Media](#media)
- [Motion](#motion)
- [Do](#do)
- [Do not](#do-not)
- [Known gaps](#known-gaps)
- [Contacts and sources](#contacts-and-sources)

## Voice

[Two or three sentences on how the site talks: register, person, what it
never says. Include any owner language rules, e.g. punctuation or phrasing
constraints, so copy edits inherit them.]

## Color

[List the real palette as semantic roles with exact values, one per line:
ground, surface, ink, secondary ink, rules/borders, and each accent. Then
state the accent budget explicitly; this is the single most protective
line in the file.]

- Where the accent MAY appear: [e.g. the italic kickers, primary action
  hover, the one signature mark]
- Where the accent must NOT appear: [e.g. body text, backgrounds, borders,
  more than one element per section]

## Typography

[The families that ship, with their files' location in the repo, their
roles, and the scale relationships. Note weights actually used. If a
face is licensed or irreplaceable, name the closest acceptable substitute
and the settings that make it match, and name what would NOT be an
acceptable substitute.]

| Role | Family | Size behavior | Weight | Case | Notes |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

## Space and shape

[The spacing rhythm (base unit, section padding behavior), the radius
logic (one system: which elements are square, which rounded, and why),
border and rule weights, and shadow/elevation policy if any.]

## Components

[Each recurring component with its non-negotiable traits: buttons (shape,
states, what a primary vs secondary looks like), cards or their
equivalent, forms, navigation. Reference the real CSS class or component
names so an editor can find them.]

## Media

[How images are treated on this site: aspect ratios, framing devices,
grade or filter policy, alt-text expectations, and where the originals
live. State clearly which images are real photography and which are
generated or stock, so future edits keep the disclosure honest.]

## Motion

[What moves, what never moves, and the reduced-motion behavior. If the
site is deliberately still, say so, so nobody adds animation to "finish"
it.]

## Do

[Five to ten short positive rules that capture this site's character,
each derived from a real decision in the build.]

## Do not

[Five to ten short rules protecting the system from its likeliest
drifts, each traceable to a real decision or owner constraint, e.g. "Do
not introduce a second accent color", "Do not use [punctuation the owner
excludes]", "Do not add stock photography; this site uses only X".]

## Known gaps

[Honesty section, always present: what this file could not capture or
the build does not settle. E.g. dark mode not designed; print styles not
designed; the licensed display face has no bundled fallback proof; email
templates not covered. A gap named here is a decision awaiting an owner,
not an invitation to improvise.]

## Contacts and sources

- Accepted build: [commit or tag this file describes]
- Fonts licensed from: [source and license note]
- Photography rights: [source and scope]
- Studio of record: [name and contact, if the owner wants it recorded]
