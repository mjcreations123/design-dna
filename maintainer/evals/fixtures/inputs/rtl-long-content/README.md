# Arabic-first long-form documentation

## Evaluation task

Repair reading, navigation, and overflow behavior for Arabic-first documentation
without shortening or translating the supplied content.

## Facts to preserve

- Arabic is the primary language and the copy is approved.
- Product identifiers, command names, URLs, and code remain left-to-right.
- The documentation uses a restrained system stack for reliable Arabic glyph
  coverage and offline availability.
- The desktop sidebar and article hierarchy are useful conventions for this
  reading task.

## Traps intentionally present

- The document is incorrectly declared `dir="ltr"`.
- Navigation and prose are physically left-aligned.
- Physical margin/padding properties do not adapt to RTL.
- The sidebar layout and breadcrumb read in the wrong direction.
- Long URL, code, and table content can overflow.
- Focus visibility and narrow-screen reflow are incomplete.

Do not “solve” the fixture by replacing Arabic with English, deleting long
content, or turning the documentation into a marketing landing page.

