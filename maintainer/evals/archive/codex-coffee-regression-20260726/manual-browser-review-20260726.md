# Manual browser review — superseded coffee concept

Archive note: retained only as a dated regression review, never release evidence.

Status: revise; this artifact is retained as a regression example and is not a
release-passing review.

## Context

- Host that created the implementation: Codex sub-agent
- Route: `http://127.0.0.1:8765/` from a temporary local-only server
- Browser: connected Chrome browser; exact version was not exposed
- Viewports inspected: 1440 × 1000 and 390 × 844
- States inspected: initial hero, mobile reflow, open disclosure, skip-link
  activation, console warnings/errors

## What held up

- The visual direction was current, forceful, and project-specific rather than
  nostalgic or built from cream/serif/sage, glass, card-grid, or generic SaaS
  defaults.
- The implementation used a local Arial/Helvetica system stack rather than a
  watched builder-default font.
- The primary heading was one text node with one foreground color.
- Narrow-screen inspection found no horizontal document overflow.
- The disclosure opened correctly, the content hierarchy remained coherent,
  and the browser reported no warning or error messages.
- Missing business facts, non-live actions, and concept status were explicit.

## Findings

1. Medium — prominent-copy fragment emphasis. The signal-board message changed
   only `COFFEE` to white through
   `.signal-board__message span:nth-child(2)`. No supplied brand, semantic,
   status, data, quotation, or editorial rule justified the one-word change.
   This exposed a loophole in the earlier heading-only rule. The runtime rule
   and scanner were broadened to cover prominent display copy regardless of
   wrapper.
2. Medium — incomplete skip-link focus transfer. Activating “Skip to content”
   changed the URL fragment to `#main`, but browser inspection still reported
   `BODY` as the active element. The accessibility baseline now requires
   verification that the bypass moves keyboard focus to a meaningful
   programmatically focusable target; hash movement alone is insufficient.

## Checks not performed

- No screen-reader session, automated accessibility scan, contrast tool,
  200/400 percent zoom, text-spacing override, network throttling, print
  dialog, or independent target-user test was performed.
- Full-page screenshot capture timed out; viewport screenshots were inspected
  in-session but were not stored as release evidence.
