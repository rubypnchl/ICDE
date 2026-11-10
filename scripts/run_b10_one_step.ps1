$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $root
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
if (!(Test-Path -LiteralPath $py)) { $py = 'python' }
Write-Host '== B10 dedicated tests =='
& $py -m unittest discover -s tests -p 'test_b10_matched_gate_pilot.py' -v
if ($LASTEXITCODE -ne 0) { throw 'B10 unit tests failed' }
Write-Host '== B10 frozen-input preflight =='
& $py .\scripts\run_b10_matched_gate_pilot.py --check-inputs
if ($LASTEXITCODE -ne 0) { throw 'B10 frozen-input preflight failed' }
Write-Host '== B10 matched-input execution =='
& $py .\scripts\run_b10_matched_gate_pilot.py
if ($LASTEXITCODE -ne 0) { throw 'B10 execution failed; no result claimed' }
Write-Host '== B10 status; nothing auto-committed =='
git status --short
Write-Host 'B10 execution SUCCESS. Inspect outputs before committing.'
