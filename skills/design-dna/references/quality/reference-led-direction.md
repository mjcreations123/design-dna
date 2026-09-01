# Reference-led direction

Use this for every fresh Enterprise Candidate public website before the first
visual candidate. It supplies a positive, project-specific direction source;
it is not a moodboard ritual, a generic gallery crawl, a popularity contest,
or permission to reproduce another brand's work.

Read the current [public reference source registry](public-reference-sources.json)
and create the project-local `reference-dossier.md` record before broad
implementation. Initialize the project with `--profile enterprise-candidate`
so the prebuild gate can hold the record; a standard-only state on a fresh
public build is an omission the gate will flag.

## Contents

- [Use only eligible public material](#use-only-eligible-public-material)
- [Retrieve the way each source allows](#retrieve-the-way-each-source-allows)
- [Check the ledger before selecting](#check-the-ledger-before-selecting)
- [Build a brief-weighted reference set](#build-a-brief-weighted-reference-set)
- [Capture what you looked at](#capture-what-you-looked-at)
- [Synthesize; do not collage or reproduce](#synthesize-do-not-collage-or-reproduce)
- [Improve beyond the set](#improve-beyond-the-set)
- [Continue autonomously](#continue-autonomously)

## Use only eligible public material

The registry identifies sources whose public material was available when it was
audited. A source may display a sign-in or pricing link and still be useful when
the actual inspiration entry is visible publicly. Select only material you can
see legitimately during the current project:

- a public live site;
- a public gallery screenshot, case study, portfolio card, or other visible
  design entry; or
- material reachable through an account the user is authorized to use.

Do not use a login, payment, subscription, security interstitial, private
entry, or browser limitation as a reason to bypass access controls. A source
that is temporarily unavailable is skipped for this project; a source whose
useful material genuinely requires restricted access remains inactive until a
future legitimate public audit changes the registry.

## Retrieve the way each source allows

Each active registry source declares a `retrieval` mode, measured at the last
audit:

- `fetch`: a plain HTTP request exposes entry links and preview images, so a
  text fetch of a gallery page or entry page is enough to find candidates.
- `browser`: entries render only in a real browser session. A plain fetch
  returns a script shell, an empty listing, or a rate-limit response. That
  result is not evidence that the source is unavailable; it is evidence that
  the wrong tool was used.

For a `browser` source, use the interactive path described in the
[render harness](render-harness.md). With the Playwright CLI the sequence is
`open <url>`, `resize 1440 900`, then `screenshot --filename <path>`; read the
current `--help` rather than relying on remembered flags, and close the
session when done. Move at a human pace on a source that rate-limits, and
never work around a limit, a login wall, or a security interstitial.

Whatever the mode, the candidate you evaluate is the visible work itself, not
the gallery's listing text. Open the entry or the live site and look at it at
a wide and a narrow width before it earns a row.

## Check the ledger before selecting

When an authorized cross-project [ledger](ledger.md) exists, read its
"references used" column for recent unrelated work before choosing this set.
Reaching for the same sites project after project is how a studio grows a
house style out of other people's work. Reuse of a recent reference needs a
brief-specific reason, recorded in the dossier's ledger-check line; without
one, choose differently. If no authorized ledger exists, record `none` and
continue.

## Build a brief-weighted reference set

Start with the visitor, category, content, material/media need, task, and
project risk. Weight the active sources accordingly rather than using the same
gallery order for every project. A baby-crib brand may learn from furniture,
children's products, premium retail, editorial photography, or trust-heavy
commerce; it is not limited to crib websites.

Record at least six strong individual references, drawn from at least three
active sources, with no single source supplying more than half of the rows.
Among live sites, no two rows may point at the same host. The floor exists
for one reason: so that no single site becomes the template. It is not a
target and not a score; add a row for every reference that earns its place,
and stop when the set has enough independent answers to the brief's real
decisions. Gallery homepages do not count as references. A public gallery
entry counts even when the linked site no longer works. For each candidate,
inspect the visible work itself and ask whether it offers a concrete,
transferable relationship for this brief:

- visitor orientation, information hierarchy, or navigation;
- product, service, editorial, or category storytelling;
- material/media casting, typography, or composition;
- comparison, selection, transaction, support, or other real interaction; or
- route progression, direct-entry clarity, and mobile behavior.

Gallery membership, an award, a large audience, an animation, or a fashionable
surface is not proof that the work fits this project. Reject a candidate when
its visible craft, content depth, route behavior, accessibility, or visitor
logic would weaken the intended encounter.

Also collect at least three weak or mismatched public examples. Describe the
specific observed relationship that fails this brief, such as empty spectacle,
unclear hierarchy, portable commerce scaffolding, inappropriate media, poor
reading behavior, or an unhelpful mobile transformation. Do not make claims
about the creator, rating, authorship, or why it appeared in a gallery.

## Capture what you looked at

Every strong and negative row binds a capture of the work as you saw it:
a PNG saved under `.design-dna/references/`, recorded in the row as
`path plus sha256:<64 lowercase hex>`. The gate verifies that the file exists,
decodes as a PNG, and matches its hash. A row without a capture is rejected,
because a reference nobody looked at is not research; it is a plausible name.

A minimal sequence with the Playwright CLI, run from the project root:

```text
playwright-cli open "https://example.test/entry"
playwright-cli resize 1440 900
playwright-cli screenshot --filename ".design-dna/references/strong-3.png"
playwright-cli close
python -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" ".design-dna/references/strong-3.png"
```

The row's capture cell is then
`.design-dna/references/strong-3.png plus sha256:<the printed digest>`.
Name captures by role and rank (`strong-3.png`, `weak-1.png`) so a reviewer
can match them to rows without opening the record. Capture the work at
the width you evaluated it at; a narrow capture may accompany the wide one
but does not replace it.

Captures are internal evidence. They stay inside `.design-dna/`, which the
deployable public root already excludes, and they are never shown to the
visitor or presented as the project's own work.

## Synthesize; do not collage or reproduce

Select a named subset of at least four strong references, drawn from at least
two sources, and map each to a real project decision. Multiple references may
inform different decisions, but the resulting website needs one project-derived
organizing logic. Do not make a Frankenstein page that assigns every section to
a different borrowed visual trick.

Public work can inform composition, hierarchy, pacing, interaction patterns,
and general visual relationships. It does not authorize copied trademarks,
logos, names, copy, photography, illustration, code, or a distinctive whole
brand page recreated as a substitute. Adapt the relevant relationship to the
actual project facts, audience, assets, and route job.

Keep the dossier and synthesis internal. They should guide the work, never
leak onto the customer-facing website as process labels, design rationale, or
back-end taxonomy.

## Improve beyond the set

The selected references are the floor for this project, not its ceiling. The
dossier's elevation line names at least one consequential decision where the
build goes further than every reference in the set: larger and more specific
real media, a category depth the references skip, a signature interaction none
of them has, a first screen that answers the visitor's question faster, or a
mobile encounter that is designed rather than collapsed. Name the decision,
say why this brief earns it, and carry it into the direction record so the
rendered closure can confirm it is visible. A build that merely matches its
references has reproduced the average of the gallery.

## Continue autonomously

Once the dossier and direction synthesis are complete, build and review the
site without waiting for a separate research approval. Pause only when a
missing fact, brand decision, rights question, cultural authority, or delivery
constraint would materially change the result.
