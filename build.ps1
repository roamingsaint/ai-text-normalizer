$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$versionFilePath = Join-Path $projectRoot "version.py"
$versionMatch = Select-String -Path $versionFilePath -Pattern 'APP_VERSION\s*=\s*"([0-9]+)\.([0-9]+)\.([0-9]+)"'
if (-not $versionMatch) {
  throw "Could not parse APP_VERSION from version.py"
}
$major = [int]$versionMatch.Matches[0].Groups[1].Value
$minor = [int]$versionMatch.Matches[0].Groups[2].Value
$patch = [int]$versionMatch.Matches[0].Groups[3].Value
$version = "$major.$minor.$patch.0"

$metaDir = Join-Path $projectRoot "build"
New-Item -ItemType Directory -Force $metaDir | Out-Null
$versionMetaPath = Join-Path $metaDir "windows-version-info.txt"

@"
# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=($major, $minor, $patch, 0),
    prodvers=($major, $minor, $patch, 0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [StringStruct('CompanyName', 'AI Text Normalizer Contributors'),
           StringStruct('FileDescription', 'AI Text Normalizer tray utility'),
           StringStruct('FileVersion', '$version'),
           StringStruct('InternalName', 'AITextNormalizer'),
           StringStruct('LegalCopyright', 'MIT License'),
           StringStruct('OriginalFilename', 'AITextNormalizer.exe'),
           StringStruct('ProductName', 'AI Text Normalizer'),
           StringStruct('ProductVersion', '$version')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Path $versionMetaPath -Encoding UTF8

python -m PyInstaller `
  --noconsole `
  --onefile `
  --name AITextNormalizer `
  --distpath release `
  --icon "assets\ai-text-normalizer.ico" `
  --version-file "$versionMetaPath" `
  --add-data "rules.json;." `
  main.py
