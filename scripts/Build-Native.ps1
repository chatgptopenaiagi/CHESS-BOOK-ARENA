$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot)
$nativeSource=Join-Path (Get-Location).Path 'native\vendor\cbvault'
$revision='ce5a582d98c3d0ac62dc10b965b4fb32d102da97'
if(-not(Test-Path $nativeSource)){
    git clone https://github.com/itshak/cbvault $nativeSource
    if($LASTEXITCODE){throw 'Native source clone failed'}
    git -C $nativeSource checkout $revision
}
$actual=git -C $nativeSource rev-parse HEAD
if($actual -ne $revision){throw 'Native source revision differs; no automatic overwrite performed'}
cargo build --release --locked --manifest-path native\arena-reader\Cargo.toml
if($LASTEXITCODE){throw 'Native build failed'}
