param([string]$DatabasePath='')
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot))
if(Get-Process CHESS-BOOK-ARENA -ErrorAction SilentlyContinue){throw 'Application is running; no update attempted'}
$registration='HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ChessBookArena_is1'
$existing=Get-ItemProperty $registration
$installedRoot=$existing.InstallLocation
$appData=Join-Path $env:LOCALAPPDATA 'ChessBookArena'
$before=@{}
Get-ChildItem $appData -File -ErrorAction SilentlyContinue | Where-Object {$_.Extension -eq '.json' -or $_.Name -like '*.sqlite*'} | ForEach-Object {$before[$_.FullName]=(Get-FileHash $_.FullName -Algorithm SHA256).Hash}
$before | ConvertTo-Json | Set-Content (Join-Path $projectRoot 'evidence\upgrade-protected-files.private.json')
$setup=Join-Path $projectRoot 'dist\CHESS-BOOK-ARENA-Setup.exe'
$install=Start-Process $setup -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/DIR=$installedRoot" -PassThru -Wait -WindowStyle Hidden
if($install.ExitCode){throw "Production installer exit $($install.ExitCode)"}
$exe=Join-Path $installedRoot 'CHESS-BOOK-ARENA.exe'
$actual=(Get-FileHash $exe -Algorithm SHA256).Hash
$expected=(Get-FileHash (Join-Path $projectRoot 'dist\CHESS-BOOK-ARENA\CHESS-BOOK-ARENA.exe') -Algorithm SHA256).Hash
if($actual -ne $expected){throw 'Production installed executable differs'}
$previousAcceptanceDatabase=$env:CBA_ACCEPTANCE_DATABASE
try{
    $env:CBA_ACCEPTANCE_DATABASE=$DatabasePath
    $data=Join-Path $projectRoot 'private\production-installed'
    $receipt=Join-Path $projectRoot 'evidence\cba002-production-installed.json'
    $run=Start-Process $exe -WorkingDirectory $env:TEMP -ArgumentList '--self-test',$receipt,'--acceptance-data',$data -Wait -PassThru -WindowStyle Hidden
    if($run.ExitCode){throw 'Production installed acceptance failed'}
    $reopened=Join-Path $projectRoot 'evidence\cba002-production-reopened.json'
    $again=Start-Process $exe -WorkingDirectory $env:TEMP -ArgumentList '--reopen-test',$reopened,'--acceptance-data',$data -Wait -PassThru -WindowStyle Hidden
    if($again.ExitCode){throw 'Production installed reopen failed'}
}finally{$env:CBA_ACCEPTANCE_DATABASE=$previousAcceptanceDatabase}
foreach($item in $before.GetEnumerator()){if((Get-FileHash $item.Key -Algorithm SHA256).Hash -ne $item.Value){throw 'A protected user catalog/settings file changed'}}
[ordered]@{status='PASS';installer_kind='production installer, existing per-user application upgraded';from_version=$existing.DisplayVersion;to_version=(Get-ItemProperty $registration).DisplayVersion;installer_exit=$install.ExitCode;installed_executable_sha256=$actual.ToLower();portable_hash_matches=$true;protected_catalog_settings_files=$before.Count;protected_files_unchanged=$true;actual_database_test=[bool]$DatabasePath;setup_sha256=(Get-FileHash $setup -Algorithm SHA256).Hash.ToLower()} | ConvertTo-Json | Set-Content (Join-Path $projectRoot 'evidence\cba002-production-upgrade.json')
