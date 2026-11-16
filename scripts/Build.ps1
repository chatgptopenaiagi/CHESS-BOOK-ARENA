$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot)
& .\scripts\Build-Native.ps1
& .\.venv\Scripts\python.exe -m pytest -q
if($LASTEXITCODE){throw 'Tests failed'}
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm CHESS-BOOK-ARENA.spec
if($LASTEXITCODE){throw 'Build failed'}
Copy-Item licenses dist\CHESS-BOOK-ARENA\licenses -Recurse -Force
Copy-Item THIRD-PARTY.md dist\CHESS-BOOK-ARENA\
Copy-Item examples dist\CHESS-BOOK-ARENA\examples -Recurse -Force
Write-Host 'Portable application: dist\CHESS-BOOK-ARENA\CHESS-BOOK-ARENA.exe'
Write-Host 'Compile scripts\installer.iss with an available Inno Setup 7 compiler for setup.exe.'
