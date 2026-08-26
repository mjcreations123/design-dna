# DESIGN.md handoff record

Use this template when a transferred or maintained repository benefits from a
client-facing `DESIGN.md`. A small static handoff, an established design-system
repository, or a client with another authoritative format may not need a new
file. When used, fill only the relevant sections from the project's accepted
system. Write from the shipped build's real tokens and decisions, never from
another brand's record and never with values the rendered site does not use.

Delete irrelevant sections and the guidance sentences in brackets when filling it in. Keep the
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

[Describe the consequential voice, terminology, and audience decisions at the
length this project needs. Include owner language rules only when they exist.]

## Color

[List the color roles and exact values that the project actually uses. When a
color's scarcity or exclusivity is part of the accepted system, record where it
belongs and where it does not. Omit accent guidance when the system has no such
contract.]

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

[Record the spacing, shape, border, and depth relationships that a future edit
must preserve. A project may have one radius family, several role-specific
families, square geometry, or no tokenized shape rule.]

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

[Add only the short positive rules a future editor needs, each derived from a
real decision in the build. Omit this section if the earlier system record is
already sufficient.]

## Do not

[Add only traceable rules that protect the system from likely drift. Do not
invent punctuation, accent-count, photography, or other prohibitions merely to
populate the list.]

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
