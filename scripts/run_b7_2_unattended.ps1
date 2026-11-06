# B7.2 unattended local batch. Read-only source data. No API/network/model calls.
# The PowerShell window must remain open and the machine must remain awake.
param(
    [Parameter(Mandatory=$true)][string]$Python,
    [switch]$SkipExistingDataMiner
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $root
$log = Join-Path $root 'data\evaluation\b7_2_batch_run.log'
if (Test-Path -LiteralPath $log) {
    Write-Error "Refusing to overwrite previous log: $log"
    exit 2
}
"B7.2 local batch START $(Get-Date -Format o)" | Set-Content -LiteralPath $log -Encoding UTF8
"Repo: $root" | Add-Content -LiteralPath $log
"Python: $Python" | Add-Content -LiteralPath $log

function Run-Step([string]$Label,[string[]]$Arguments) {
    "=== $Label $(Get-Date -Format o) ===" | Tee-Object -FilePath $log -Append
    & $Python @Arguments 2>&1 | Tee-Object -FilePath $log -Append
    $code=$LASTEXITCODE
    if ($code -ne 0) { throw "STEP FAILED ($code): $Label; see $log" }
}
try {
    Run-Step 'B7.2 tests' @('-m','unittest','discover','-s','tests','-p','test_b7_2_candidate_screen.py','-v')
    Run-Step 'B7.2 inputs' @('.\scripts\run_b7_2_candidate_screen.py','--check-inputs')
    Run-Step 'B7.2 four-domain candidate screen' @('.\scripts\run_b7_2_candidate_screen.py','--run')
    if (-not $SkipExistingDataMiner) {
        $output=Join-Path $root 'data\evaluation\b7_2_existing_dataonly_discovery.json'
        if (Test-Path -LiteralPath $output) { throw "Refusing overwrite of data-mining output: $output" }
        # Existing repository data-only mining: AI4I + SEC, a DIFFERENT input regime.
        Run-Step 'Existing data-only discovery (manufacturing + finance, NOT matched metadata-only)' @('-m','src.rule_discovery','--output','data/evaluation/b7_2_existing_dataonly_discovery.json')
    }
    "B7.2 batch COMPLETE $(Get-Date -Format o)" | Tee-Object -FilePath $log -Append
    "Results: data/evaluation/b7_2_candidate_screen/; inspect summary.json and README.md" | Tee-Object -FilePath $log -Append
    exit 0
} catch {
    "B7.2 batch STOPPED: $_" | Tee-Object -FilePath $log -Append
    exit 2
}
