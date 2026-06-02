# OBDM Test Runbook

Run these checks from the project root before handing over a build:

```powershell
cd "C:\Users\82108\OneDrive\문서\Data exchange Platform"
python -m compileall app.py data_marketplace tests
python tests\schema_migration_test.py
python tests\seed_demo_test.py
python tests\smoke_test.py
python tests\ui_text_smoke_test.py
python tests\route_access_test.py
python tests\review_summary_test.py
python tests\upload_failure_ux_test.py
python tests\admin_review_ui_test.py
python tests\admin_resubmission_review_test.py
python tests\seller_dataset_progress_test.py
python tests\dataset_resubmission_test.py
python tests\seller_product_report_test.py
python tests\purchase_flow_test.py
python tests\order_license_test.py
python tests\order_payment_workflow_test.py
python tests\payment_access_gate_test.py
python tests\pricing_buyer_orders_test.py
python tests\download_limit_test.py
python tests\api_limit_test.py
python tests\payment_gateway_interface_test.py
python tests\operations_checklist_test.py
python tests\database_backup_test.py
python tests\admin_settlement_test.py
python tests\admin_csv_export_test.py
python tests\security_regression_test.py
```

Expected pass markers:

- `SMOKE_TEST_PASS`
- `UI_TEXT_SMOKE_TEST_PASS`
- `ROUTE_ACCESS_TEST_PASS`
- `SCHEMA_MIGRATION_TEST_PASS`
- `SEED_DEMO_TEST_PASS`
- `API_LIMIT_TEST_PASS`
- `DOWNLOAD_LIMIT_TEST_PASS`
- `ORDER_LICENSE_TEST_PASS`
- `ORDER_PAYMENT_WORKFLOW_TEST_PASS`
- `PAYMENT_ACCESS_GATE_TEST_PASS`
- `ADMIN_SETTLEMENT_TEST_PASS`
- `PRICING_BUYER_ORDERS_TEST_PASS`
- `PAYMENT_GATEWAY_INTERFACE_TEST_PASS`
- `OPERATIONS_CHECKLIST_TEST_PASS`
- `DATABASE_BACKUP_TEST_PASS`
- `ADMIN_CSV_EXPORT_TEST_PASS`
- `SECURITY_REGRESSION_TEST_PASS`
- `REVIEW_SUMMARY_TEST_PASS`
- `UPLOAD_FAILURE_UX_TEST_PASS`
- `ADMIN_REVIEW_UI_TEST_PASS`
- `ADMIN_RESUBMISSION_REVIEW_TEST_PASS`
- `SELLER_DATASET_PROGRESS_TEST_PASS`
- `DATASET_RESUBMISSION_TEST_PASS`
- `SELLER_PRODUCT_REPORT_TEST_PASS`
- `PURCHASE_FLOW_TEST_PASS`

Coverage focus:

- Public pages and policy pages render.
- SQLite schema and migration baseline are current.
- Demo seed data can create a seller, buyer, active product, and approved purchase request.
- API key usage limits block over-limit sample API calls.
- Sample download limits block over-limit buyer downloads.
- Product license fields, prepared orders, and seller revenue summaries work.
- Manual payment status transitions move orders through requested, paid, failed, and canceled states.
- Paid products require completed payment before sample download and API key access.
- Admin settlement summaries calculate seller paid amount, platform fee, and settlement due amount.
- Product pricing models and buyer order history pages render correctly.
- Payment gateway preparation records provider references and payment event history.
- Admin operations checklist shows release settings, retention policy, schema status, and test criteria.
- Admin-only SQLite backup download returns a database file and blocks anonymous or normal users.
- Admin operational reports export CSV files with expected headers.
- Security regression checks cover admin-only CSV exports, CSRF, API key handling, and cross-user access.
- Authenticated user pages render.
- Admin pages require admin role.
- Market and product APIs respond.
- Korean UI labels and OBDM brand text remain stable.
- Validation review summary logic works.
- Upload processing failures show customer-facing recovery guidance.
- Admin review screens show decision signals and approval checklist.
- Admin review screens show resubmission source and follow-up history.
- Seller dashboard shows uploaded dataset progress and next actions.
- Rejected datasets can be resubmitted with parent dataset tracking and history views.
- Seller product operations report aggregates purchases, orders, downloads, and API usage.
- Purchase detail and seller purchase request flow work.

Latest full regression status:

- Step 51 full regression pass completed.
- Compile check passed.
- All listed test scripts passed with their expected pass markers.
