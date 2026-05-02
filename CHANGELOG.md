# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

## [1.0.5] - 2026-05-03

### Changed
- Removed automatic update checks when opening Settings.
- Kept update results inside the Settings `Updates` section for manual checks.

## [1.0.4] - 2026-04-30

### Changed
- Removed the automatic Settings-open update check; update checks are manual from the Settings `Updates` section.

## [1.0.3] - 2026-04-30

### Changed
- Update availability now appears inside the Settings `Updates` section instead of a separate popup.

## [1.0.2] - 2026-04-30

### Changed
- Simplified Settings UI back to the basic rules and app-update flow.
- Replaced JSON rules files with `rules.toml` and moved rule guidance into inline TOML comments.
- Opening Settings now performs a quiet background app update check.

## [1.0.1] - 2026-04-30

### Added
- TOML-based rules files with comment support in bundled and live defaults.

### Changed
- Live rules now use `rules.toml` instead of `rules.json`.
- Existing `rules.json` files are migrated forward to `rules.toml` on first run.

## [1.0.0] - 2026-04-30

### Added
- Settings UX where only `Normalize hotkey` is editable and `Preview hotkey` is auto-derived as `Alt + Normalize`.
- Rules management actions in Settings: open live rules, view bundled defaults, reset live rules.
- In-app update check action in Settings.
- Windows build metadata and icon embedding in `build.ps1`.
- GitHub issue templates for bug reports and feature requests.
- Portable ZIP release asset in GitHub Actions.
- Versioned default rules metadata with live-rules update status in Settings.

### Changed
- Tray menu simplified to Normalize, Toggle preview, Settings, Exit.
- Hotkey suppression enabled to reduce shortcut leakage into target apps.
- Default dash normalization now converts direct em/en dash joins like `role—owning` to `role - owning`.

## [0.3.0] - 2026-04-14

### Added
- In-app update checks against GitHub Releases.
- Improved release workflow with checksum publishing.
