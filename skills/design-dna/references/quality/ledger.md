# The studio ledger

One row per shipped build, recording the choice axes that form a fingerprint.
Sameness across the studio's own builds is the deepest tell: a beautiful
choice repeated becomes a house style, and the owner kills builds for it.
Two QA builds from one batch once shipped the same skeleton in different
paint, and the same display family shipped on four separate projects. The
ledger is the mechanism that prevents both.

## Where it lives

`~/.claude/design-dna/LEDGER.md` (create the directory on first use). It
deliberately lives OUTSIDE the skill package, so reinstalling or syncing the
skill never erases it, and OUTSIDE every client repo, per the owner's rule
that studio notes never ship in client git history. Row format is in
[the ledger template](../../templates/ledger-template.md).

## What a row records

Minimized choice axes only, never confidential client content: project name,
date, surface mode, display family, body family, palette poles, layout
skeleton in one phrase, the signature move, motion language, and one-line
notes. This minimization is what makes the ledger standing owner
authorization for cross-project comparison under the privacy rules in the
[specificity review](specificity-review.md).

## The two duties

**Consult before directing.** At direction time, before the first candidate,
read the last five rows. The rotation test, two parts, both mandatory:

1. The display family MUST NOT repeat from the previous build, and no two
   builds in one batch may share a family.
2. The macrostructure MUST NOT repeat: if the proposed hero composition,
   headline scale and case, eyebrow treatment, section rhythm, and footer
   form match either of the previous two rows, the direction has already
   failed and goes back to candidates.

**Append on ship.** Appending this build's row is part of shipping; the
[preship gate](../../templates/preship-gate.md) blocks without it. A
revision to an existing build updates its row rather than adding one.

## What the ledger is not

Not a quality record, not a client deliverable, not a place for rejected
candidates (those live in the project's own `.design-dna/`), and never a
menu: repeating a PAST choice is the failure; picking from past choices as
a shortcut is the same failure earlier.
