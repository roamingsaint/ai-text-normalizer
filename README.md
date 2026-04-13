# AI Text Normalizer

## Run It

Build the Windows EXE:

```powershell
python -m pip install -r requirements.txt
.\build.ps1
```

Run the app:

```text
release\AITextNormalizer.exe
```

## Use It

- `Ctrl+Shift+Q` normalizes the current selection
- `Ctrl+Alt+Shift+Q` opens preview first
- The app stays in the tray while running
- Right-click the tray icon for `Settings...`, `Check for updates`, and `Open rules.json`

Edit `rules.json` to change replacements. See `RULES.md` for rule format and ordering.

## Share It

For Windows users, distribute the GitHub release asset:

- `AITextNormalizer.exe`
- `AITextNormalizer.exe.sha256`

Users do not need Python installed. They download the EXE from GitHub Releases and run it directly.

## Publish Updates

1. Update `version.py`
2. Commit and push the change
3. Create and push a tag like `v0.3.0`

```powershell
git tag v0.3.0
git push origin v0.3.0
```

GitHub Actions will build the EXE, generate a SHA-256 checksum, and attach both files to the GitHub Release.

## Update Checks

The tray menu has `Check for updates`.

It checks the latest GitHub Release for `roamingsaint/ai-text-normalizer`, compares it to the app's current version, and opens the release download page if a newer version is available.
