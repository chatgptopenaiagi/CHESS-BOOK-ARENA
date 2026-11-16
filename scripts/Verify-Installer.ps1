$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot))
$testInstall=[IO.Path]::GetFullPath((Join-Path $projectRoot 'evidence\installed'))
if(-not $testInstall.StartsWith($projectRoot+[IO.Path]::DirectorySeparatorChar)){throw 'Install test path escaped project'}
$setup=Join-Path $projectRoot 'dist\CHESS-BOOK-ARENA-Setup.exe'
$p=Start-Process -FilePath $setup -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/DIR=$testInstall" -PassThru -Wait -WindowStyle Hidden
if($p.ExitCode){throw "Install exit $($p.ExitCode)"}
$exe=Join-Path $testInstall 'CHESS-BOOK-ARENA.exe'
$expected=(Get-FileHash (Join-Path $projectRoot 'dist\CHESS-BOOK-ARENA\CHESS-BOOK-ARENA.exe') -Algorithm SHA256).Hash
$actual=(Get-FileHash $exe -Algorithm SHA256).Hash
if($expected -ne $actual){throw 'Installed executable hash mismatch'}
$receipt=Join-Path $projectRoot 'evidence\installed-acceptance.json'
$run=Start-Process -FilePath $exe -WorkingDirectory $env:TEMP -ArgumentList '--self-test',$receipt -PassThru -Wait -WindowStyle Hidden
if($run.ExitCode){throw 'Installed executable acceptance failed'}
$result=Get-Content $receipt -Raw | ConvertFrom-Json
if($result.status -ne 'PASS'){throw 'Installed receipt failed'}
$un=Start-Process -FilePath (Join-Path $testInstall 'unins000.exe') -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART' -PassThru -Wait -WindowStyle Hidden
if($un.ExitCode){throw 'Uninstall failed'}
$removed=-not(Test-Path $exe)
if(-not $removed){throw 'Uninstall left executable'}
[ordered]@{status='PASS';install_exit=$p.ExitCode;installed_sha256=$actual.ToLower();portable_hash_matches=$true;installed_acceptance=$result.status;uninstall_exit=$un.ExitCode;executable_removed=$removed;setup_sha256=(Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()} | ConvertTo-Json | Set-Content (Join-Path $projectRoot 'evidence\installer-verification.json')
