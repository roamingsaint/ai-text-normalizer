# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Settings UX where only `Normalize hotkey` is editable and `Preview hotkey` is auto-derived as `Alt + Normalize`.
- Rules management actions in Settings: open live rules, view bundled defaults, reset live rules.
- In-app update check action in Settings.
- Windows build metadata and icon embedding in `build.ps1`.
- GitHub issue templates for bug reports and feature requests.
- Portable ZIP release asset in GitHub Actions.

### Changed
- Tray menu simplified to Normalize, Toggle preview, Settings, Exit.
- Hotkey suppression enabled to reduce shortcut leakage into target apps.

## [0.3.0] - 2026-04-14

### Added
- In-app update checks against GitHub Releases.
- Improved release workflow with checksum publishing.
