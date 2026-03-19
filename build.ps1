$ErrorActionPreference = "Stop"

python -m PyInstaller `
  --noconsole `
  --onefile `
  --name TextPolish `
  --distpath release `
  --add-data "rules.json;." `
  main.py
