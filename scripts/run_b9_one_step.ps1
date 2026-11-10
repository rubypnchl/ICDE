$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repo = Split-Path -Parent $PSScriptRoot
$py = 'C:\Users\nrr136.CAMPUS\AppData\Local\Programs\Python\Python312\python.exe'
if (-not (Test-Path -LiteralPath $py)) { $py = 'python' }
Push-Location $repo
try {
    Write-Host '== B9 dedicated unit tests =='
    & $py -m unittest discover -s tests -p 'test_b9_runtime_comparison.py' -v
    if ($LASTEXITCODE -ne 0) { throw 'B9 tests failed' }
    Write-Host '== B9 frozen-source preflight =='
    & $py .\scripts\run_b9_runtime_comparison.py --preflight
    if ($LASTEXITCODE -ne 0) { throw 'Frozen sources failed B9 preflight' }
    Write-Host '== B9 nine-repetition matched-source benchmark =='
    & $py .\scripts\run_b9_runtime_comparison.py --run
    if ($LASTEXITCODE -ne 0) { throw 'B9 benchmark failed' }
    Write-Host '== Git working tree; no commit performed =='
    git status --short
    Write-Host 'B9 SUCCESS. Check data/evaluation/b9_runtime_results_v1.json before any publication.'
} finally { Pop-Location }
