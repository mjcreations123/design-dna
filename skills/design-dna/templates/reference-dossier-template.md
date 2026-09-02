---
schema_version: 1
created_with: "__DESIGN_DNA_VERSION__"
classification: "internal"
evidence_contract: "proportional-evidence-v1"
record_status: "draft"
---

# Reference dossier

Use this internal record for the required public-reference research before a
fresh Enterprise Candidate website is implemented. It is a project-specific
decision record, not customer-facing copy, a moodboard, an award score, or a
license to reproduce another brand's work.

Every reference row binds a capture you actually looked at. Save captures
under `.design-dna/references/` and bind each one as
`path plus sha256:<64 lowercase hex>`. A row without a capture is a row the
prebuild gate rejects; the capture is the evidence that the research happened.
For a strong reference the capture comes from a scroll sequence the producer
watched, because a single full-page still can only show what does not move
and will always miss the reason the site is good.

## Research frame

- Brief and priority-source rationale:
- Current active registry audit date and limitations:
- Authorized-account basis, if any; otherwise `none`:
- Public-access disposition for blocked or unavailable sources:
- Ledger check (prior references reused, with reason, or `none`):

## Strong references

Record at least six references drawn from at least three active sources, with
no single source supplying more than half of the rows. The floor exists so
that no one site becomes the template; it is not a target. Add rows for every
reference that earns its place. Number ranks 1 through N without gaps.

| Rank | Reference title or visible entry | Public URL or gallery-entry URL | Discovery source | Retrieval date | Access status | Capture path and SHA-256 | Signature (what a stranger would name) | Brief relevance | Design to copy | Rights boundary |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |  |  |
| 2 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |  |  |
| 3 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |  |  |
| 4 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |  |  |
| 5 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |  |  |
| 6 |  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |  |  |

The rank reflects fit for this exact brief, not a universal quality score.
Every row's `Signature` cell answers one question first: if a stranger were
shown this site, what would they say they noticed about its design? That is
almost always something the page does rather than something that sits there,
and it is written from a scroll sequence the producer watched, never from a
single still. The `Design to copy` cell then names the good parts taken from
that reference in concrete terms, behavior first (what the page does as it
scrolls, its interaction and transitions, its signature moment, then media
treatment, composition, how its color behaves, its type posture and scale,
shapes and surfaces), and then names the parts left behind and why. A part
that a thousand strangers would not have noticed is not the takeaway and
does not belong in the cell. The
build uses the brand's own palette and typefaces chosen for beauty; the
reference contributes behavior, composition, and scale, not its values or
family names. The `Rights boundary` cell names only what is not reused: the
reference's logo, name, copy, photographs, illustrations, and code. A gallery
entry is sufficient when it is publicly viewable; a live URL is not required.

## Negative counterexamples

| Reference title or visible entry | Public URL or gallery-entry URL | Discovery source | Retrieval date | Access status | Capture path and SHA-256 | Observed mismatch or weak relationship | What this project must avoid |
| --- | --- | --- | --- | --- | --- | --- | --- |
|  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |
|  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |
|  |  |  |  | public-live / public-gallery-entry / authorized-account |  |  |  |

Describe visible consequences, not a judgment of the creator or why the entry
was curated. These are counterexamples for the current brief, not permanent
style bans.

## Selected synthesis

- Selected positive ranks (at least four distinct, from at least two sources):
- Project-specific organizing synthesis:
- Behavior copied and where it is rendered:
- Negative-counterevidence result:
- Elevation beyond the references (what this build does that none of them do):
- Direction record path and status:

| Selected rank(s) | Design copied and destination | Project-specific adaptation | Boundary or verification |
| --- | --- | --- | --- |
|  |  |  |  |

This table is the design transfer map. Each row names which reference's
front-end design is copied and which route, section, or system role of this
project receives it (first screen, comparison route, product hero, type
system, palette, motion language, phone recomposition). At least one row
carries behavior, not only static composition: the `Behavior copied and where
it is rendered` line above names it and the route whose rendered scroll
sequence proves it. Different routes may
take parts from different references, but the site is one design: the
brand's palette, one type system of at most two families chosen for beauty,
one rhythm where each section flows into the next; sections from different
references that change voice at every screen fail the record. The references are the floor for this
project, not its ceiling: the elevation line names where the build goes
further than any of them.
