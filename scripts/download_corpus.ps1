# Downloads the Phase 1 BNM PDFs listed in corpus/sources.csv into corpus/raw/.
# Run from the repo root on Windows: powershell -ExecutionPolicy Bypass -File scripts/download_corpus.ps1
$dir = Join-Path $PSScriptRoot "..\corpus\raw"
New-Item -ItemType Directory -Force $dir | Out-Null
Import-Csv (Join-Path $PSScriptRoot "..\corpus\sources.csv") | ForEach-Object {
  try { Invoke-WebRequest $_.source_url -OutFile (Join-Path $dir $_.file) -UserAgent "Mozilla/5.0"; "ok   $($_.file)" }
  catch { "FAIL $($_.file)  $($_.Exception.Message)" }
}
