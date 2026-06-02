# OBDM Operations Checklist

This checklist is the first release-stabilization baseline for OBDM.

## Environment

- Set `FLASK_SECRET_KEY` before production-like testing.
- Rotate the default admin bootstrap credentials:
  - `ADMIN_EMAIL`
  - `ADMIN_PASSWORD`
- Use `.env.example` as a reference only; the app reads process environment variables and does not load `.env` automatically.
- Keep the current DBMS as SQLite for now:
  - `database/marketplace.db`
- Confirm the Flask app starts and `/health` returns `200`.

## File Retention

Current MVP policy:

- Uploaded source files are deleted after validation.
- Normalized CSV files are not retained unless explicitly configured.
- Sample files are retained for seller/admin/buyer preview according to access rules.
- PII details remain visible only to the uploader/seller and admins.

Relevant settings:

- `DELETE_UPLOADED_FILES_AFTER_PROCESSING`
- `KEEP_NORMALIZED_DATA`
- `KEEP_SAMPLES`
- `SAMPLE_SIZE`

## Storage Directories

Check these paths before running uploads:

- `uploads/`
- `converted_csv/`
- `samples/`
- `reports/`
- `database/`

## Database

- Run schema migration checks before release.
- Confirm `schema_migrations` contains every expected version.
- Back up `database/marketplace.db` before manual operational testing or migration.
- Admin backup route:
  - `/web/admin/database-backup.sqlite`
- Only admins can download the SQLite backup file.
- Every backup download records `DATABASE_BACKUP_DOWNLOADED` in `audit_logs`.
- Store downloaded backup files outside the public web directory.

## Security

- Confirm admin-only pages return `403` to normal users.
- Confirm anonymous users are redirected away from authenticated pages.
- Confirm CSV report exports are admin-only.
- Confirm POST forms require CSRF tokens.
- Confirm API data access requires approved purchase and payment completion where applicable.

## Payment

The MVP payment workflow is still manual, but it now records gateway-ready fields:

- `orders.payment_provider`
- `orders.payment_reference`
- `payment_events`

Real PG integration still needs provider contract setup, webhook signature verification, idempotency, and retry rules.

## Test Run

Run at least:

```powershell
python -m compileall app.py data_marketplace tests
python tests\operations_checklist_test.py
python tests\route_access_test.py
python tests\ui_text_smoke_test.py
python tests\schema_migration_test.py
python tests\security_regression_test.py
```

For a full local pass, run:

```powershell
.\scripts\run_regression.ps1
```

If local PowerShell script execution is restricted, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_regression.ps1
```

Full regression criteria remain documented in `TESTING.md`.
