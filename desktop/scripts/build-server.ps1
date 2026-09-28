param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
$desktopRoot = Split-Path -Parent $PSScriptRoot
$legacyRoot = Split-Path -Parent $desktopRoot
Push-Location $desktopRoot
try {
    & $Python (Join-Path $PSScriptRoot 'extract-legacy-exports.py')
    if ($LASTEXITCODE -ne 0) { throw 'Échec de la préparation des exports existants.' }
    & $Python -m PyInstaller --noconfirm --clean --onedir --noconsole --name MarassimServer --distpath server-dist --workpath server-build --specpath server-build --paths $legacyRoot --paths (Join-Path $desktopRoot 'server') --add-data ((Join-Path $legacyRoot 'template') + ';template') --add-data ((Join-Path $desktopRoot 'assets/marassim-logo.png') + ';desktop/assets') --hidden-import database --hidden-import config --hidden-import db --hidden-import access_control --hidden-import rules --hidden-import contract_generator --hidden-import excel_export --hidden-import legacy_exports --hidden-import online_exports (Join-Path $desktopRoot 'server/app.py')
    if ($LASTEXITCODE -ne 0) { throw 'Échec de la compilation du serveur.' }
} finally { Pop-Location }
