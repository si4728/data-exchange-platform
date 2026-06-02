param(
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

if (-not $Python) {
    if ($env:PYTHON) {
        $Python = $env:PYTHON
    } else {
        $PythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if ($PythonCommand) {
            $Python = $PythonCommand.Source
        }
    }
}

if (-not $Python) {
    $BundledPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path $BundledPython) {
        $Python = $BundledPython
    }
}

if (-not $Python -or -not (Test-Path $Python)) {
    throw "Python executable not found. Pass -Python <path> or set the PYTHON environment variable."
}

Write-Host "Using Python: $Python"

& $Python -m compileall app.py data_marketplace tests
if ($LASTEXITCODE -ne 0) {
    throw "Compile check failed."
}

$Tests = @(
    "tests\schema_migration_test.py",
    "tests\seed_demo_test.py",
    "tests\smoke_test.py",
    "tests\ui_text_smoke_test.py",
    "tests\route_access_test.py",
    "tests\review_summary_test.py",
    "tests\upload_failure_ux_test.py",
    "tests\admin_review_ui_test.py",
    "tests\admin_resubmission_review_test.py",
    "tests\seller_dataset_progress_test.py",
    "tests\dataset_resubmission_test.py",
    "tests\seller_product_report_test.py",
    "tests\purchase_flow_test.py",
    "tests\order_license_test.py",
    "tests\order_payment_workflow_test.py",
    "tests\payment_access_gate_test.py",
    "tests\pricing_buyer_orders_test.py",
    "tests\download_limit_test.py",
    "tests\api_limit_test.py",
    "tests\payment_gateway_interface_test.py",
    "tests\operations_checklist_test.py",
    "tests\database_backup_test.py",
    "tests\admin_settlement_test.py",
    "tests\admin_csv_export_test.py",
    "tests\security_regression_test.py"
)

foreach ($Test in $Tests) {
    Write-Host "Running $Test"
    & $Python $Test
    if ($LASTEXITCODE -ne 0) {
        throw "Regression test failed: $Test"
    }
}

Write-Host "FULL_REGRESSION_PASS"
