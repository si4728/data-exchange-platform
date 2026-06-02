# Repository Instructions

## Project

This repository is the OBDM data exchange platform MVP. It is a Flask and SQLite application for dataset validation, marketplace publication, purchase requests, manual payment handling, API/sample access, seller reporting, and admin operations.

## Working Rules

- Keep changes scoped to the requested feature or fix.
- Prefer the existing Flask route, Jinja template, and `data_marketplace.database` helper patterns.
- Keep SQLite as the DBMS unless the user explicitly asks for a migration.
- Do not commit generated runtime data from `uploads/`, `converted_csv/`, `samples/`, `reports/`, or `database/*.db`.
- Treat PII handling, payment access gates, API keys, admin-only exports, and cross-user access as high-risk areas.
- Preserve Korean UI labels unless the task explicitly asks to change copy.
- Avoid introducing new dependencies unless they clearly reduce implementation risk or match an existing project pattern.

## Verification

Use the project root as the working directory.

Preferred compile check:

```powershell
python -m compileall app.py data_marketplace tests
```

If `python` is not on PATH in Codex desktop, use:

```powershell
& 'C:\Users\82108\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m compileall app.py data_marketplace tests
```

For behavior changes, run the focused regression test in `tests/` plus any adjacent tests listed in `TESTING.md`.

For security-sensitive changes, run:

```powershell
python tests\route_access_test.py
python tests\security_regression_test.py
```

If using the bundled Python runtime:

```powershell
& 'C:\Users\82108\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\route_access_test.py
& 'C:\Users\82108\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tests\security_regression_test.py
```

## Review Guidelines

- Check that admin routes remain admin-only.
- Check that sellers cannot access or mutate other sellers' datasets, products, purchases, or reports.
- Check that buyers only receive sample/API access after the required purchase and payment state.
- Check that PII details stay limited to seller/admin review surfaces.
- Check that CSRF expectations remain intact for POST forms.
- Check that database migrations are idempotent and covered by `schema_migration_test.py`.
