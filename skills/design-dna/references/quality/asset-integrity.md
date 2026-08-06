# Asset integrity and art direction

Use this for logos, photography, illustration, video, audio, fonts, product
imagery, maps, screenshots, generated media, and third-party embeds.

## Contents

- [Record provenance](#record-provenance)
- [Generated and synthetic material](#generated-and-synthetic-material)
- [Preserve truth](#preserve-truth)
- [Direct and implement](#direct-and-implement)
- [Release gate](#release-gate)

## Record provenance

The current asset-manifest schema version is 2. Use a durable manifest when the
selected Asset-led assurance, public-use risk, or maintenance need makes the
record useful. Do not make a production provenance dossier a prerequisite to
sketching or comparing visual directions. During exploration, preserve the
minimum source, authorization, factual-status, and rights notes needed to keep
the work honest; initialize a project record with
`init_project_state.py --record assets` when the durable gate applies.
Before composing the first entry, print the complete, schema-valid,
release-blocked example with:

```text
python -B "<DESIGN_DNA_SKILL_ROOT>/scripts/init_project_state.py" --print-asset-example
```

Copy an entry into `.design-dna/assets.yml`, replace every instructional value,
and run `--check-state`. Do not copy the example as project evidence: its
`placeholder`, `pending`, and unresolved rights fields intentionally prevent a
public-release interpretation.

For every material asset entered in the durable manifest, record the applicable
evidence below. Interpret fields by the asset's real type, role, stage, and
risk; an explicit, reasoned `not-applicable` decision is better than invented
detail:

- stable ID and usage location;
- asset type: image, video, audio, font, document, map, embed, or other;
- publication status for the asset itself: internal-only, planned-public,
  public, or prohibited. `planned-public` records intended exposure and
  activates public-use review; it is not approval or readiness. Publication
  status is separate from the privacy classification of the provenance
  record;
- source, creator, and obtained date;
- when a source URL is recorded, use an absolute `http` or `https` URL with a
  valid hostname and no embedded credentials or fragment;
- a project-relative source path and exact SHA-256 when a local source file
  exists. Validation fails when the file is missing, escapes the project, or
  changes after review;
- owner-supplied, first-party, licensed, generated, or other origin;
- license, terms, attribution, and modification limits;
- factual status: approved, concept, placeholder, or prohibited;
- privacy-review status; a completed or `not-required` decision needs an
  accountable reviewer, date, and reason;
- owner approval status, accountable owner, decision date, reason, and
  replacement status;
- alt text, caption, transcript, or decorative decision;
- source and output dimensions, format, and optimization.

`art_direction` is optional and extensible. Omit it when the asset's
`content_job`, delivery, and accessibility records already say what reviewers
need. When a distinct creative decision needs a durable note, use a nonempty
string or project-defined string keys; do not fill a standard subject, crop,
palette, lighting, perspective, set-consistency, or other aesthetic checklist.

Interpret the delivery fields by type rather than forcing every asset into an
image workflow:

| Type | Required delivery/review meaning |
| --- | --- |
| image | intrinsic dimensions, focal/crop behavior, formats, narrow and changed-breakpoint crop proof |
| video | frame dimensions, poster/fallback, captions or transcript as applicable, controls, reduced-data behavior, responsive frame proof |
| audio | duration/channels where material, transcript or equivalent access where applicable, controls, preload/failure behavior; no visual crop evidence |
| font | exact binary and license binding, actual formats/axes, subset/source, preload decision, fallback and failure behavior |
| document | page/format identity, accessible alternative, download/open behavior, current-version owner |
| map | source and license, privacy/network boundary, non-map address or directions fallback, keyboard/touch behavior |
| embed | source and permission, privacy/consent boundary, loading/error/refusal fallback, intrinsic space |
| other | name the real technical characteristics and why the generic fields are sufficient |

For image and video assets, unresolved intrinsic space blocks readiness. For
fonts, missing license, format, or loading/fallback evidence blocks readiness.
Do not write fake pixel dimensions for audio, fonts, documents, maps, or
embeds; record the type-relevant characteristic in the existing delivery
field and say `not-applicable` only with a real reason.

Do not treat a public URL as permission to reuse.

Rows migrated from asset-manifest schema 1 carry
`migration_review.required: true` and remain readiness-blocked. Resolve each
unresolved field from evidence, review the inferred type and exposure, and
only then set `required: false`; never clear the flag merely to pass the gate.

## Generated and synthetic material

Scale the review to stage, claim, audience risk, and intended publication. An
internal illustrative exploration needs enough evidence to preserve authority,
asset identity, factual boundaries, visual inspection, and the next approval
decision; it does not need invented jurisdictional, credential, or legal-review
theater. Planned-public and public uses follow the additional manifest gate
below. A resolved `not-applicable` provenance decision or `not-required` legal
decision is legitimate when an accountable owner records its real basis; it is
not a shortcut around an applicable law, platform rule, contract, or owner gate.

- Confirm that either an explicit current instruction from an accountable
  owner or `generated_concept_media: allow` in the active project policy
  authorizes this exact use. `ask` is not permission, and a need for sensory
  media does not authorize generation.
- Record the authorization basis, tool or model, source inputs, exact prompt
  or a `sha256:` digest with 64 lowercase hexadecimal characters,
  timezone-qualified generation date, selected output, rejected outputs and
  reasons, material edits, final usage, and accountable approval. Preserve
  project-bound outputs in the project rather than relying on a temporary tool
  location.
- Bind the selected final output as `source_path` plus `source_sha256`. Record
  text-only direction inputs with a `text:` prefix; bind every material file
  input with a project-relative path and SHA-256. A prose filename is not
  source evidence.
- Bind the source asset, contact/review sheet, and every applicable
  responsive-crop or state proof with
  project-relative paths and exact SHA-256 values. A list of filenames, an
  unbound screenshot, or a temporary generation URL is not review evidence.
- Write an asset-specific artifact inspection covering the things that could
  plausibly fail in that image: text and marks, anatomy, geometry, repeated
  objects, reflections, shadows, material joins, perspective, continuity,
  cultural representation, and mismatch between crop and claimed subject.
  Do not treat the checklist as a claim that every category was applicable.
- Review the actual crop at the narrowest intended public width and at any
  breakpoint where the composition changes. The crop must preserve the
  asset's content job, not merely keep pixels on screen.
- Do not use generated people, places, products, documents, or screenshots as
  factual proof.
- Record a concept-disclosure decision as `required`, `not-required`, or
  `pending`, with a recorded rationale for every resolved decision. The
  separate owner-approval fields bind the accountable owner and date. When
  disclosure is required, bind one exact public wording across the base asset
  and any jurisdiction-specific provenance record.
- Check text, logos, objects, anatomy, reflections, continuity, and
  representational harm.
- For public use, determine whether jurisdiction-specific generated-media
  provenance duties apply and whether the project acts as a provider, deployer,
  publisher, or another regulated role. Do not guess a jurisdiction or legal
  role merely to populate a record; route material legal interpretation to
  qualified counsel when an applicable gate requires it.
- Record the transformation chain and whether machine-readable provenance was
  detected, validated, and preserved. Credentials can carry provenance; their
  presence does not prove truth, and their absence does not prove undisclosed
  origin.
- Record the basis and accessible wording for any visible disclosure. Legal
  review, machine-readable provenance, and audience-facing disclosure are
  separate checks.
- Attribute every completed legal-review decision to an accountable reviewer,
  date, and rationale; `not-required` is a decision, not an empty shortcut.
- When the base generation record and jurisdiction-specific provenance record
  both repeat disclosure wording, keep the audience-facing text identical so
  two records cannot silently authorize conflicting disclosures.
- Before public release of generated media, resolve applicability and legal
  review, name the jurisdiction, record the transformation chain, and record
  explicit credential-detection, validation, and preservation outcomes.
  `changes-required`, `rejected`, `pending`, or unresolved legal status blocks
  planned-public and public use; only an attributable `approved` or
  `not-required` decision can close that field.

The manifest's top-level `classification` controls handling of the provenance
record. Each asset's `publication_status` controls whether public-use gates
apply. An internal provenance file can—and usually should—describe a public
asset, so record classification must never be used as a shortcut around public
generated-media review.

Generated concept media can be the right concept or final creative asset when
the owner explicitly authorizes it and the page needs atmosphere,
materiality, spatial context, or a human-use scene. Its factual limit does not
require a photo-free site; it requires an honest role, provenance, inspection,
disclosure when applicable, and an explicit replacement decision. A final
approved use may record replacement as `not-needed`. Keep disclosure
proportionate and do not repeat it through ordinary marketing copy.

## Preserve truth

- Do not fabricate logos, customer marks, awards, reviews, people, products,
  places, interfaces, or events.
- Do not present a concept render as a real feature or existing place.
- Verify screenshot data and remove private or stale information.
- Label demo data and generated imagery when viewers could mistake them for
  evidence.
- Keep branded, legal, safety, dietary, allergen, and accessibility claims
  owner-approved.

## Direct and implement

- Give each asset a truthful role. It may be functional, documentary,
  explanatory, editorial, aesthetic, atmospheric, ceremonial, ornamental, or
  compositional; a decorative asset does not need an invented information or
  interaction job.
- For image-dependent subjects, verify that the final set actually carries
  recognition, atmosphere, scale, use, or material detail. Diagrams, grids,
  decorative SVG, and interface chrome do not count merely because they occupy
  visual space.
- Make the relationship among source, crop, grade, perspective, and treatment
  intentional. Coherence may include heterogeneous archives, documentary
  variation, deliberate contrast, or route-local media systems; do not
  cosmetically regularize the set into implausible uniformity.
- Preserve logo clear space, proportions, contrast, and approved variants.
- Use responsive sources and reserve intrinsic dimensions.
- Avoid embedding third parties when a static or privacy-preserving alternative
  serves the task.
- Define the missing, blocked, slow, and replacement state.

## Release gate

Block public release when a visible asset is an unresolved placeholder or
lacks known rights, required attribution, factual approval, privacy review,
generated-media authorization and review where applicable, or type-relevant
delivery evidence such as responsive-crop proof for images and video. Record
approvals rather than inferring them. A placeholder row may remain
structurally valid while its source is unknown, but `planned-public` records
intent only and does not by itself mean release-ready.

For an asset-led readiness claim, `assets: []` is not evidence. Every recorded
asset must have an approved or clearly bounded concept status, an approved or
not-required privacy decision, explicit owner approval, resolved accessibility
treatment, and no outstanding replacement requirement. Planned-public or
public generated assets also need recorded license or usage terms. Use
`--check-ready`; ordinary `--check-state` intentionally distinguishes a valid
draft record from an asset record that is ready within the listed project-state
scope. That result does not establish unlisted specialist review or whole-site
production readiness.
