$ErrorActionPreference = "Stop"

python -m PyInstaller `
  --noconsole `
  --onefile `
  --name AITextNormalizer `
  --distpath release `
  --add-data "rules.json;." `
  main.py
