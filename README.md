# AI Text Normalizer

Tired of em-dashes and weird quotes in AI output?
Run AI Text Normalizer to turn that into clean, normal human text.

## Platform support

Current support:
- Windows only

Not supported yet:
- Linux
- macOS
- iOS
- Android

The current app is a Windows tray utility with Windows-specific global hotkey, clipboard, and text replacement behavior.

This can still evolve in the same repo later by keeping the normalization engine and rules shared, while adding separate platform-specific app layers for Windows, Linux, and any future mobile implementation.

## What it fixes by default

- `—` and `–` to standard dash formatting
- Curly quotes to straight quotes (`“ ”` -> `"`, `‘ ’` -> `'`)
- Ellipsis (`…`) to `...`
- Non-breaking spaces to regular spaces

You can extend or change these rules in Settings via `Open live rules.toml`.

## Install (Windows users)

1. Open the GitHub Releases page for the project.
2. Download one of:
   - `AITextNormalizer.exe`
   - `AITextNormalizer-portable.zip`
3. Run `AITextNormalizer.exe`.

No Python installation is required for end users.

## Build from source

```powershell
python -m pip install -r requirements.txt
.\build.ps1
```

## Run local build

```text
release\AITextNormalizer.exe
```

## Current behavior

- Tray menu: `Normalize selected text now`, `Toggle preview before replace`, `Settings...`, `Exit`
- `Normalize hotkey` is editable in Settings
- `Preview hotkey` is auto-derived as `Alt + Normalize` and is non-editable
- Any `alt` entered in Normalize is ignored
- Rules and updates are managed from Settings

## Hotkey rules

In Settings:
- Only Normalize is editable
- Preview is generated automatically
- Normalize must include at least 3 keys
- Normalize must include one non-modifier key (for example: `q`, `n`, `f8`)
- Example: `ctrl+shift+q` => preview `ctrl+alt+shift+q`

## Rules and updates

In Settings:
- `Open live rules.toml`
- `View bundled defaults`
- `Reset live rules to defaults`
- `Check for updates (vX.Y.Z)`

Rules format and ordering are documented in [RULES.md](/C:/DEV/TextNormalizer/RULES.md).

## Update check behavior

When local version is outdated and you click `Check for updates`:
- The app checks the latest GitHub release via API.
- It opens the latest release EXE asset download URL when available.
- If no EXE asset URL is found, it opens the release page.

## Share (Windows)

Distribute from GitHub Releases:
- `AITextNormalizer.exe`
- `AITextNormalizer.exe.sha256`
- `AITextNormalizer-portable.zip`

## Known limitations

- Some apps block synthetic copy/paste and will not normalize reliably.
- Secure or protected input fields are unsupported.
- Shortcut conflicts can still happen with aggressive app-level hotkey handlers.

## Publish updates

1. Update [version.py](/C:/DEV/TextNormalizer/version.py)
2. Commit and push
3. Tag and push, for example:

```powershell
git tag v1.0.1
git push origin v1.0.1
```

GitHub Actions will build and publish EXE, checksum, and portable ZIP assets.
