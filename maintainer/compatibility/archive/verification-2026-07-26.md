# Historical host installation verification — 2026-07-26

This record covers static package validity and installed-file parity only. It
does not claim behavioral invocation, host-native telemetry, perceptual quality,
or rendered accessibility review.

## Release identity

- Package: `design-dna`
- Version: `2.0.0`
- Canonical runtime SHA-256:
  `f7e1b77215ad016265f64cb4942655cd65b0f2dda079021ad2d54ad4a8968a7f`
- Canonical runtime files: `50`

## Codex

- Intended route: `~/.agents/skills/design-dna`
- The official Codex skill quick validator returned `Skill is valid!` for the
  canonical runtime and the installed route.
- Transactional sync parity returned the canonical SHA-256 above for source and
  target, with `50` source files, `50` target files, and no warning.
- Complete discovery scanning across `.agents/skills`, `.codex/skills`,
  `.codex/plugins/cache`, and `.claude/skills` found this as the only Codex
  `design-dna` route.
- The Codex desktop executable could not be invoked as a standalone CLI from
  this PowerShell session (`Access is denied`). No trusted host-native adapter
  is registered, so controlled behavioral and rendered release checks remain
  pending.

## Claude Code

- Intended route: `~/.claude/skills/design-dna`
- The official Codex skill quick validator returned `Skill is valid!` for the
  installed route; this verifies the portable `SKILL.md` package contract, not
  Claude behavior.
- Transactional sync parity returned the canonical SHA-256 above for source and
  target, with `50` source files, `50` target files, and no warning.
- Complete discovery scanning found this as the only Claude `design-dna` route.
- Claude Code `2.1.219` returned:
  `{"loggedIn":false,"authMethod":"none","apiProvider":"firstParty"}`.
  Behavioral and rendered checks are therefore blocked until Claude Code is
  authenticated in a new or refreshed session.

## Route scan note

The complete route scan emitted one safe warning for the Codex Chrome plugin
cache's `latest` reparse alias because its in-root versioned target was scanned
directly. It found no duplicate, unexpected, or drifted `design-dna` route.
