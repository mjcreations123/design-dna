# Owner-policy onboarding

The bundled `policy/owner-defaults.yml` contains portable publisher guidance.
It is not buyer approval. Project facts, explicit instructions, accessibility,
safety, law, rights, and brand requirements outrank it.

When an accountable owner wants project-specific governance:

1. copy `templates/owner-policy.example.yml` to
   `PROJECT/.design-dna/owner-policy.yml`;
2. replace `owner` and `scope`; add, remove, or rename scoped concern IDs;
   review each disposition and interpretation; then change `status` from
   `draft` to `active`;
3. preserve the schema version and supported disposition values; concern IDs
   are project-extensible and must describe outcomes or governance concerns,
   not ingredient bans;
4. run `scripts/scan_project.py`, which discovers the project-local policy, or
   pass another exact file with `--owner-policy`;
5. retain the reviewed policy with the project rather than changing the
   distributable package.

This is the one deliberate exception to the evidence-record initializer:
owner policy is opt-in governance, not generated evidence. Never copy it
unresolved, never activate placeholder identities, and never imply that its
preferences prove human authorship or objective design quality.

If no accountable owner approves a project policy, the scanner uses the
bundled publisher guidance and the delivery must retain that boundary.

An owner policy is not a brand brief. Every project still needs its own facts,
audience, content hierarchy, visual direction, rights record, and rendered
review. `sensory_media_strategy` decides whether the subject needs a meaningful
media path; it does not authorize image generation.
`generated_concept_media` separately records `prohibit`, `ask`, or `allow` for
the exact policy scope. An explicit user instruction in the current task may
serve as that authorization, but it must still be recorded with the asset
evidence and cannot authorize fabricated documentary proof.

Do not use owner policy to create a portable taste doctrine. Font families,
pairing counts, palettes, styles, motifs, shapes, section recipes, motion
grammars, media counts, and concept counts belong in an approved project or
brand scope when the owner genuinely wants them. The bundled policy may ask
for investigation of a rendered pattern; it must not turn that pattern into a
universal prohibition or preferred substitute.
