# Media retention

Owner directive, Motty (MJ's Studio), 2026-11-02:

> "The design DNA stuff: there's no need for them anymore. Once I approve a
> design, we don't need to keep all the screenshots anymore. You could delete
> them right away. You just need to look at them. You could get rid of all the
> garbage that there's no need for. Just get rid of it."

> "Make sure you don't delete anything that will have an actual effect on
> things that we are in the middle of working on."

## Working material and the record

Working material, kept only while the design is open:

- study frames, first screens, region captures, contact sheets and
  storyboards (`references/<id>/...`);
- check frames, review sheets, early-look sheets and recordings
  (`check/runs/<timestamp>/...`, `check/*.png`);
- candidates sheets, ad hoc screenshots and gap-inspection captures anywhere
  under `.design-dna`;
- screen recordings (`.webm`, `.mp4`, `.mov`) and raw capture frames (`.gray`);
- any browser profile captured under `.design-dna` (a folder holding
  `Local State` or `Default/Preferences`, with caches such as
  `optimization_guide_model_store/.../model.tflite`).

The record, kept: `plan.json`, `sheet.md`, `study.json`, `check.json`,
`latest.json`, `review.md`, typeface match records, notes, logs, fonts, and
`retention.json`. These name every capture by path and SHA-256, so the design
stays traceable after the pictures are gone.

## When

Only after the owner approves the design, recorded in the plan as
`"approval": { "by": "Motty", "date": "YYYY-MM-DD" }`. Record it when he says
so and never on his behalf; `check_build.mjs` reports the same field on its
`APPROVAL` line. Before approval the captures are what he and the reviewer
look at, and absolute 8 (no shortcuts) still requires them. If he asks for
changes after approving, that is a design in progress again: do not clean it
until he approves the revision and the plan carries the new date.

## How

```
node <skill>/scripts/clean_media.mjs --project <PROJECT>                 # report only
node <skill>/scripts/clean_media.mjs --project <PROJECT> --apply         # remove
node <skill>/scripts/clean_media.mjs --project <PROJECT> --apply --keep client-designs
```

1. Run the report. It lists what would go by folder, every browser profile,
   and anything it refuses on.
2. Read it. Client-supplied images, brand files, or an image the site itself
   loads from `.design-dna` are not screenshots: protect them with `--keep`
   (a path relative to `.design-dna`; repeatable).
3. Run with `--apply`. The tool hashes each file, writes `retention.json`,
   removes the files and profiles, removes folders it emptied, and writes the
   final status. Report its totals.

It refuses, removing nothing, when: the plan has no `approval` with both `by`
and `date`; the plan still says TODO; a file was written after the approval
date; anything under `.design-dna` changed in the last ten minutes; the
legacy `.design-dna.lock` is active or unreadable; or the folder is
`~/.design-dna` (the owner record, evidence and reviews), a link, or missing.
`--approved` is the operator's statement that the owner approved the design as
it now stands. Use it only for a project whose plan has no approval field (a
pre-13 layout) or to confirm that his approval covers later work; never to get
past a refusal on a guess. Nothing confirms the ten-minute quiet window
except waiting.

## After cleaning

A cleaned project is not re-checkable as it stands: `check_build.mjs` needs
the captures that `gap_reviews`, signature evidence and review transfers name.
A revision starts with fresh studies (`study_reference.mjs`), a new check and a
new approval. The hashes in the record and `retention.json` remain the
provenance of what was compared.

## Browser profiles

The study and check tools launch the installed Google Chrome with a
throwaway profile in the operating system's temporary folder and close it when
the run ends. Never point a browser's user-data directory inside the project or
`.design-dna` (see [render harness](render-harness.md)). A profile found there
is garbage from an earlier ad hoc capture; the cleanup removes it after
approval. A profile still in use by a running browser fails the quiet window
or cannot be removed, and the tool reports it in `not_removed`.

## Out of scope

The tool cleans one project's `.design-dna` and nothing else: never the site,
never another task's project, never `~/.design-dna`, and never install backups.
Deleting by hand in place of the tool loses the hash record and the guards.
