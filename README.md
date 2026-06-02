# OBDM Data Exchange Platform

OBDM is a Flask-based MVP for validating, reviewing, publishing, and selling datasets through a lightweight data marketplace workflow.

The current build keeps SQLite as the DBMS and focuses on the full MVP path: upload, validation, admin review, market publication, purchase requests, manual payment handling, API/sample access controls, seller reporting, admin exports, and operational backup/audit support.

## Features

- Dataset upload and validation for CSV, JSON, JSON Lines, delimited text, and plain text files
- Schema profiling, PII detection, quality scoring, sample generation, and duplicate detection
- Seller dashboard with dataset progress, resubmission tracking, product management, purchase requests, and product operations reporting
- Admin review workflows for datasets, products, users, purchases, settlements, audit logs, CSV exports, and SQLite backup downloads
- Marketplace catalog with search, filters, sorting, pagination, tags, categories, product detail pages, and favorites
- Purchase request, order, license, manual payment status, and payment-event workflows
- API key issuance, API usage limits, sample download limits, and payment-based access gates
- Release operations checklist and security regression coverage

## Project Structure

```text
app.py                         Flask routes, views, API endpoints, and app bootstrap
data_marketplace/
  config.py                    Storage paths and retention settings
  database.py                  SQLite schema, migrations, and data access helpers
  payments.py                  Payment status transition service
  seed_demo.py                 Demo seller, buyer, product, and purchase seed data
  services.py                  Validation orchestration and report summaries
  validators/                  File conversion, schema, PII, duplicate, quality, sample logic
templates/                     Jinja2 web UI templates
tests/                         Script-style regression tests
DEVELOPMENT_STEPS.md           Implementation history through Step 62
OPERATIONS_CHECKLIST.md        Production-readiness checklist
TESTING.md                     Full regression runbook
```

## Requirements

- Python 3.11 or newer recommended
- Flask 3.x
- pandas 2.2+

Install dependencies:

```powershell
pip install -r requirements.txt
```

If `python` is not on PATH in the local Codex desktop environment, use the bundled runtime:

```powershell
C:\Users\82108\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe
```

## Environment

Copy `.env.example` values into your shell environment before production-like testing. The app reads environment variables through `os.getenv`; it does not load `.env` files automatically.

PowerShell example:

```powershell
$env:FLASK_SECRET_KEY="replace-with-a-long-random-secret"
$env:ADMIN_EMAIL="admin@example.com"
$env:ADMIN_PASSWORD="replace-this-before-release"
```

## Run Locally

From the project root:

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000/
```

Health check:

```text
http://127.0.0.1:5000/health
```

## Demo And Default Accounts

The app bootstraps a default admin account unless overridden:

```text
email: admin@example.com
password: admin1234
```

Demo seed data creates:

```text
seller: seller.demo@obdm.local
buyer: buyer.demo@obdm.local
password: demo1234
```

Do not use default credentials in production-like environments. Set `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `FLASK_SECRET_KEY` before release testing.

## Test

Compile check:

```powershell
python -m compileall app.py data_marketplace tests
```

Run the full regression suite listed in `TESTING.md`, or use the PowerShell runner:

```powershell
.\scripts\run_regression.ps1
```

If local PowerShell script execution is restricted, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_regression.ps1
```

If `python` is unavailable, pass the bundled runtime:

```powershell
.\scripts\run_regression.ps1 -Python 'C:\Users\82108\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
```

## Storage And Retention

Default MVP policy:

- Uploaded source files are deleted after validation.
- Normalized CSV files are not retained unless configured.
- Sample CSV files are retained for seller, admin, and approved buyer preview.
- Full validation reports are retained in SQLite and `reports/`.

Generated runtime data is intentionally ignored by git:

```text
uploads/
converted_csv/
samples/
reports/
database/*.db
```

## Release Checklist

Before production-like use:

- Set `FLASK_SECRET_KEY`.
- Rotate default admin credentials.
- Confirm `/health` returns `200`.
- Run schema migration and security regression tests.
- Confirm admin-only routes, CSV exports, and database backup downloads are protected.
- Back up `database/marketplace.db` before manual migration or operational testing.
- Review the manual payment workflow before real payment gateway integration.

See `OPERATIONS_CHECKLIST.md` for the full checklist.

## GitHub Repository

Repository:

```text
https://github.com/si4728/data-exchange-platform
```

Default branch:

```text
main
```
