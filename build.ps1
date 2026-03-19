$ErrorActionPreference = "Stop"

py -3 -m PyInstaller `
  --noconsole `
  --onefile `
  --name TextPolish `
  --distpath release `
  --add-data "rules.json;." `
  main.py
