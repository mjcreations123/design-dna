# Preserve the selected experience

Use this with the existing reference sheet, plan and check. It adds no shared
slots or new workflow stage. The plan is checked before the browser opens.

## Study the region that matters

After looking at the live reference, name its actual defining region:

```
node <skill>/scripts/study_reference.mjs --url <URL> --id <ID> --region ".source-region" --out .design-dna/references
```

`--region` can be repeated. It captures each named region at both widths,
including its media, relative child arrangement, and screenshot identity in
`study.json.pages[].regions`. Use the exact inner-page URL as the study's URL
when the chosen signature lives there. Never use a loader, obstructing notice
or unobserved canvas as evidence of the experience behind it.

## Add the obligation to the plan

Every substantial reference has one `signature_spec` with exact `page` and
`selector`, plus `wide` and `narrow` definitions. Each definition names:

- `kind`: static or interactive.
- `medium`: image, video, canvas, svg, background, or typography.
- `composition`: the important arrangement and image/type relationship.
- `driver`: static, scroll, time, hover, pointer, or click.
- `mechanisms`: the selected mechanism names, supported by observed evidence.
- `sequence`: the ordered states the visitor sees, using meaningful names.
- `pacing`: how the sequence progresses or why the static composition holds.
- `evidence`: image/video `{file, sha256}` bindings relative to that reference's
  study directory. Include the region capture. Interactive signatures need
  a recording or distinct frames for the sequence, not one still.

Static signatures are valid and have an empty mechanism list, driver static,
and a single settled sequence state. A region with measured dynamic content
cannot be relabeled static to discard its behavior. Choose a genuinely static
source region if that is what the design needs. If a detector cannot measure a
defining custom interaction, keep it unverified and obtain targeted evidence;
do not rename it into a supported effect or invent a static substitute.

Example transfer inside an existing planned build section:

```json
{
  "selector": ".featured-homes",
  "reference": "housing-source",
  "signature_from": ["housing-source"],
  "behavior": "swap",
  "signature_transfer": {
    "wide": {
      "reference": "housing-source",
      "medium": "image",
      "driver": "scroll",
      "mechanisms": ["swap"],
      "sequence": ["first home", "second home"],
      "steps": [
        {"action": "rest", "expect": {"selector": ".first-home", "visibility": "visible"}},
        {"action": "scroll", "delta": 600, "expect": {"selector": ".second-home", "visibility": "visible", "text": "Second home"}}
      ]
    }
  }
}
```

This illustrates the additional fields only: retain content, composition,
image_role, typography_role and mobile fields. Supply a narrow transfer too,
based on the source's actual narrow experience. Deltas, selectors, states and
text must come from the intended build, never copy example values blindly.

Each transfer starts with rest. Later actions preserve the selected driver.
Scroll uses a bounded delta and optional axis x; time uses ms (1-15000).
Hover, pointer and click name a target inside the section. Each expected
outcome names a selector inside it (or :scope), visible/hidden, and optional
text. Clicks are limited to safe disclosure controls; sending forms, adding
orders and other consequential flows require separately authorized testing.
The checker captures these states for the visual review. It cannot infer
that an input was meaningful merely because a screenshot changed.

Every route's `system_sections` names its opening, navigation and ending
selectors. These sections belong to its dominant reference. Other substantial
references contribute their selected signatures in distinct mapped regions.
Each `signature_from` entry must have the corresponding transfer. References
marked `role: "ancillary"` may provide palette/type details but do not count
toward the four substantial references and cannot own composition/behavior.

Run the inexpensive prebuild check:

```
node <skill>/scripts/check_build.mjs --plan .design-dna/plan.json --studies .design-dna/references --out .design-dna/check --plan-only
```

Plan success establishes obligations and evidence presence. It is not a build
pass or a visual judgment. The ordinary checker also runs it automatically.

## Gaps: inspected or excluded

Every gap review specifies `disposition: "inspected"` or `"excluded"`.
Inspected means new state evidence, not the original obstructed screenshot.
Excluded records exact `excluded_selectors`; an exclusion on the signature's
page also explains `unrelated_reason`. Excluding the signature region itself,
the whole page, or leaving the defining experience unverified means replacing
that contributor or re-studying it. Excluding an unrelated footer is allowed.
These records make the decision inspectable; a reviewer must verify the
claimed relationship rather than treating prose or file hashes as proof.

## Review the captured result

Keep review.md for the independent or self-review narrative and visitor walk.
In `plan.review.transfers`, add one row per mapped signature and width:
`route`, `selector`, `reference`, `viewport`, and `status` (present, missing,
unverified). Address composition, crop, hierarchy, pacing, sequence,
interaction, and image_accuracy. Bind `evidence` for both sides, using
`side: "source"` and `side: "build"`, file and SHA-256. These paths are
relative to the plan directory; for example `references/source/frames/...`
and `check/runs/.../frames/...`.

Review changed states too: filtered results, empty/filled baskets, selected
options, revealed panels and the end of held stages. Product and cultural
imagery must fit what the page says. A button working is not proof that the
result looks or reads properly.

List findings in `plan.review.issues` with severity material/minor, status
open/resolved and message. Missing/unverified transfers, material open issues,
or an incomplete visitor walk fail the final command. Do not mark a missing
signature as present merely to clear the check. The tool verifies records and
measured behavior, while the review remains accountable human/agent judgment.

Retain the first failed check and its captures, review them, then rerun after
updating the review. Any visible code/content change requires a new capture
and review. Owner approval is always separate from review completion.
