# Owner-policy onboarding

The runtime file
`skills/design-dna/policy/owner-defaults.yml` contains portable publisher
guidance. It is not buyer approval. It remains subordinate to project facts,
user instructions, accessibility, safety, law, rights, and brand requirements.

For an accountable owner:

1. copy `skills/design-dna/templates/owner-policy.example.yml` to
   `PROJECT/.design-dna/owner-policy.yml`;
2. replace `owner` and `scope`, review every preference, exception, and
   interpretation, then change `status` from `draft` to `active`;
3. preserve the schema version and allowed values;
4. run the scanner, which discovers that project-local file automatically, or
   pass a different exact path with `--owner-policy`;
5. retain the reviewed policy with the project rather than changing the
   distributable package.

Do not silently present the publisher defaults as a buyer's preferences. Do
not turn preferences into claims that a design is human-authored, undetectable,
or objectively superior. If no accountable owner has approved a project
policy, the scanner uses the bundled publisher guidance and the delivery must
retain that boundary.

An owner policy is not a brand brief. Each project still needs its own facts,
audience, content hierarchy, visual direction, rights record, and rendered
review.

`sensory_media_strategy` decides whether the subject needs a meaningful media
path; it does not authorize generation. `generated_concept_media` separately
records `prohibit`, `ask`, or `allow` for the exact policy scope. The bundled
publisher value `ask` is not permission. An explicit current instruction from
an accountable owner may authorize the named use, but the project must still
record that basis in each affected asset and satisfy provenance, rights,
inspection, disclosure, privacy, factual-boundary, and approval requirements.
