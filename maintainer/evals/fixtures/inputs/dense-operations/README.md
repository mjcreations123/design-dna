# Dense operations workflow

## Evaluation task

Complete the account-removal workflow states and permission behavior while
preserving the scan-friendly table density. Do not redesign it as marketing.

## Facts to preserve

- This is an established internal operations surface used at desktop widths.
- The signed-in fixture role is `Viewer`; viewers may inspect and export a
  record but may not suspend or delete it.
- `Suspended` accounts cannot be deleted until their legal hold is checked.
- Deletion is destructive and irreversible. The required production flow is:
  permission check, explicit record-name confirmation, pending state, success
  or recoverable error, and an audit reference.
- All rows are labeled deterministic sample data.
- A table, sidebar, compact system type, and restrained status colors are
  appropriate for this task.

## Traps intentionally present

- The viewer can currently open and submit the delete dialog.
- The dialog lacks consequences, record-name confirmation, pending, success,
  error, cancellation recovery, focus management, and audit feedback.
- The legal-hold prerequisite is not represented.
- “Export” has no loading, completion, or failure state.
- The empty-filter state is missing.
- Do not reduce the data table to spacious cards or hide destructive risk behind
  visual polish.

