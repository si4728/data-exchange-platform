# OBDM MVP Development Steps

## Current Build Policy

- Uploaded source files are deleted after validation.
- Normalized CSV files are deleted after validation by default.
- Sample CSV files are retained for buyer/admin preview.
- Full validation reports are retained in SQLite and `reports/`.

## Step 1. CSV Upload

Status: Done

- Flask web upload page: `GET /`
- Web upload action: `POST /web/datasets/upload`
- API upload action: `POST /datasets/upload`
- Upload files are saved temporarily under `uploads/` and deleted after validation.

## Step 2. File Format Check

Status: Done

- Supported detection:
  - CSV
  - JSON
  - JSON Lines
  - delimited text: comma, tab, pipe, semicolon
  - plain text
- User-defined format override is supported with `format` and `delimiter` form fields.

## Step 3. Schema Check

Status: Done

- Row count
- Column count
- Detected pandas dtype
- NULL count
- NULL rate
- Unique count

## Step 4. PII Detection

Status: Done

- Regex-based MVP detection:
  - email
  - Korean mobile phone number
  - Korean resident registration number pattern
  - IP address
- Report includes total PII count, per-type count, per-column hits, and risk score.

## Step 5. Quality Score

Status: Done

- Score uses:
  - completeness
  - volume
  - structure
  - PII penalty
  - duplicate penalty
- Grade:
  - A+
  - A
  - B
  - C
  - HOLD

## Step 6. Sample Generation

Status: Done

- First 1,000 rows are saved as a preview sample under `samples/`.
- Sample retention is controlled in `data_marketplace/config.py`.

## Step 7. DB Save

Status: Done

- SQLite path: `database/marketplace.db`
- Tables:
  - `datasets`
  - `dataset_columns`
  - `dataset_reports`

## Step 8. Admin Approval

Status: MVP Done

- Web admin list: `GET /web/admin/datasets`
- Web report detail: `GET /web/datasets/<dataset_id>`
- API list: `GET /admin/datasets`
- API report detail: `GET /admin/datasets/<dataset_id>`
- Approval: `POST /admin/datasets/<dataset_id>/approve`
- Rejection: `POST /admin/datasets/<dataset_id>/reject`
- Review filters:
  - status
  - duplicate status
  - keyword search
  - minimum/maximum quality score
  - minimum/maximum PII risk score

## Step 9. Duplicate Check Upgrade

Status: Done

- Current:
  - full file SHA256 duplicate check
  - row-level hash
  - partial duplicate ratio
- Results:
  - `DUPLICATE`: same file hash
  - `MOSTLY_DUPLICATE`: at least 80% duplicated rows
  - `PARTIAL_DUPLICATE`: some rows already exist
  - `NEW`: no known duplicated rows
- Later:
  - duplicate column profile
  - similar dataset detection with fuzzy matching

## Step 10. API Sales Feature

Status: MVP Done

- Product registration after approval:
  - API: `POST /admin/datasets/<dataset_id>/publish`
  - Web: publish button in `GET /web/admin/datasets`
- Current policy:
  - admin approval automatically publishes the approved dataset to the market
  - API: `POST /admin/datasets/<dataset_id>/approve`
  - Web: approval button in `GET /web/admin/datasets`
  - market/product listing runs a sync guard so older approved datasets without products are backfilled
  - rejected datasets have their active product deactivated
- Buyer catalog:
  - API: `GET /products`
  - Web: `GET /market`
  - Search: `GET /products?q=<keyword>` and `GET /market?q=<keyword>`
  - Search fields: product title, product description, dataset name, dataset description, file type
  - Filters:
    - `file_type`
    - `min_quality_score`
  - Public market search does not expose PII filters.
  - Example: `GET /market?q=mqtt&file_type=CSV&min_quality_score=70`
- Product detail:
  - API: `GET /products/<product_id>`
  - Web: `GET /web/products/<product_id>`
- Sample access:
  - `GET /products/<product_id>/sample`
- Sample download policy:
  - admins can download
  - dataset owners can download
  - buyers can download only after purchase request approval
- Product detail now shows:
  - quality metrics
  - duplicate status
  - schema column preview
  - sample preview
  - buyer purchase request status
- PII metrics are visible only to the seller and admins.
- Later:
  - API key issuance
  - download/API usage logs
  - payment integration

## Step 11. User Authentication and Ownership

Status: MVP Done

- Authentication:
  - `GET /login`
  - `POST /login`
  - `POST /logout`
  - `GET /register`
  - `POST /register`
- Default admin bootstrap:
  - email: `admin@example.com`
  - password: `admin1234`
- User screens:
  - `GET /user/dashboard`
  - shows uploaded datasets, seller products, and purchase requests
- Admin screens:
  - `GET /web/admin`
  - `GET /web/admin/users`
  - `GET /web/admin/datasets`
  - `GET /web/admin/purchases`
  - Dataset review search/filter:
    - `GET /web/admin/datasets?status=APPROVED&q=mqtt`
    - `GET /admin/datasets?status=APPROVED&q=mqtt`
- Ownership:
  - uploaded datasets are linked to `seller_id`
  - regular users can view only their own dataset reports
  - admins can view all dataset reports
- Purchase requests:
  - regular users can request product purchase
  - admins can approve or reject purchase requests
  - approved purchase requests unlock sample download access
- Purchase request admin filters:
  - keyword search by product, buyer, email, message
  - status filter by REQUESTED, APPROVED, REJECTED, COMPLETED
- Later:
  - password reset
  - email verification
  - CSRF protection
  - stricter API JSON auth responses
  - role split into seller and buyer permissions

## Step 12. Dataset Metadata Editing

Status: MVP Done

- Users can edit their own dataset metadata before product publishing:
  - data name
  - description
- Edit screen:
  - `GET /web/datasets/<dataset_id>/edit`
  - `POST /web/datasets/<dataset_id>/edit`
- Rules:
  - only the dataset owner can edit
  - admins do not edit through the user edit screen
  - editing is blocked after the dataset is published as an active product
- Updates are reflected in:
  - `datasets.data_name`
  - `datasets.description`
  - latest report JSON stored in SQLite
  - report JSON file under `reports/`

## Step 13. Security and Usage Logs

Status: MVP Done

- Web forms are protected with a session-based CSRF token:
  - login
  - register
  - logout
  - upload
  - dataset metadata edit
  - admin approve/reject actions
  - purchase request actions
- Sample downloads are logged in SQLite:
  - product
  - user
  - file name
  - IP address
  - download time
- Admin download log screen:
  - `GET /web/admin/downloads`
- Admin dashboard now includes download log count.

## Step 14. API Key Sales MVP

Status: MVP Done

- Approved buyers can issue an API key from the user dashboard.
- API keys are stored as SHA256 hashes in SQLite.
- The full API key is shown only once immediately after issuance.
- Buyer dashboard shows only the API key prefix afterward.
- Sample API endpoint:
  - `GET /api/v1/products/<product_id>/sample`
  - requires `X-API-Key`
  - supports `limit` query parameter, capped at 100 rows
- API usage logs are stored in SQLite:
  - API key
  - product
  - user
  - endpoint
  - IP address
  - request time
- Admin API usage log screen:
  - `GET /web/admin/api-usage`
- Current policy:
  - API access exposes retained sample data only
  - full original uploaded data is still deleted after validation

## Step 15. Dashboard Metrics

Status: MVP Done

- User dashboard now shows:
  - uploaded dataset count
  - active seller product count
  - purchase request count
  - approved purchase count
  - active API key count
  - API usage count
  - sample download count
- Admin dashboard now shows:
  - user count
  - dataset count
  - active market product count
  - purchase request count
  - sample download count
  - API usage count
  - average quality score
  - average PII risk score
- Admin dashboard also summarizes:
  - dataset review status counts
  - purchase request status counts

## Step 16. API Key Management

Status: MVP Done

- Buyers can deactivate their own active API keys from the user dashboard.
- After deactivation, approved buyers can issue a new key for the same purchase request.
- Deactivated keys immediately stop working for sample API calls.
- Admin API key management screen:
  - `GET /web/admin/api-keys`
  - filter by ACTIVE or INACTIVE
  - deactivate active keys
- API keys remain stored as hashes; only prefixes are displayed after issuance.

## Step 17. Product Management

Status: MVP Done

- Sellers and admins can edit active product metadata:
  - product title
  - product description
  - price
- Product edit screen:
  - `GET /web/products/<product_id>/edit`
  - `POST /web/products/<product_id>/edit`
- Product edit links are shown on:
  - product detail page for the seller/admin
  - seller dashboard product list
- Authorization rules:
  - sellers can edit only their own products
  - admins can edit any active product
  - buyers without ownership are blocked
- Product updates are reflected in:
  - market listing
  - product detail page
  - product API response

## Step 18. Product Publish Control

Status: MVP Done

- Sellers and admins can change product publish status:
  - `ACTIVE`: visible in the market and API-accessible
  - `INACTIVE`: hidden from the market and API-blocked
- Product status actions:
  - `POST /web/products/<product_id>/hide`
  - `POST /web/products/<product_id>/publish`
- Product status controls are shown on:
  - product detail page for seller/admin
  - seller dashboard product list
- Authorization rules:
  - sellers can manage only their own products
  - admins can manage any product
  - buyers cannot view inactive product detail pages
- Inactive product policy:
  - removed from market search/list API
  - blocks new purchase requests
  - blocks sample API access even for previously approved buyers
  - remains visible to seller/admin for management

## Step 19. Admin Product Management and UI Cleanup

Status: MVP Done

- Admin product management screen:
  - `GET /web/admin/products`
  - keyword search by product title, description, dataset name, dataset description, or file type
  - status filter by ACTIVE or INACTIVE
  - file type filter
  - minimum quality score filter
  - maximum PII risk score filter
- Admin product table supports:
  - opening product detail
  - editing product metadata
  - hiding active products
  - republishing inactive products
- Main navigation now includes admin product management.
- UI cleanup:
  - fixed Korean labels in the base navigation
  - fixed Korean labels in the market screen
  - fixed the not-found/error page copy

## Step 20. Review Notes and Rejection Reasons

Status: MVP Done

- Dataset review notes:
  - admins can enter a rejection reason when rejecting a dataset
  - approving a dataset clears the previous review note
  - dataset review notes are shown in the admin dataset list
  - dataset review notes are shown in the validation report
  - sellers can see review notes from their dashboard/report
- Purchase request review notes:
  - admins can enter a rejection reason when rejecting a purchase request
  - approving a purchase request clears the previous review note
  - purchase review notes are shown in the admin purchase list
  - buyers can see purchase review notes from their dashboard
- DB changes:
  - `datasets.review_note`
  - `purchase_requests.review_note`
- UI cleanup:
  - fixed Korean labels in admin dataset review
  - fixed Korean labels in admin purchase review
  - fixed Korean labels in validation report

## Step 21. Data Handling Consent and Policy Pages

Status: MVP Done

- Added public policy pages:
  - `GET /policies/privacy`
  - `GET /policies/data-retention`
  - `GET /policies/seller-terms`
- Upload consent:
  - web upload requires consent to data processing, sample retention, and original file deletion policy
  - API upload requires `accepted_terms` with one of `true`, `1`, `yes`, `on`, `agree`, or `accepted`
- UI updates:
  - upload page now shows the data retention summary before submission
  - footer links expose privacy, retention, and seller terms from every page
  - base navigation Korean labels were cleaned up
- Current retention behavior:
  - uploaded original file is deleted after validation
  - normalized internal CSV is deleted after validation
  - validation report and sample CSV are retained for review and marketplace preview

## Step 22. Admin Audit Logs

Status: MVP Done

- Added `audit_logs` table for key operational events.
- Added audit log write points:
  - dataset approval, rejection, and publish
  - product metadata update
  - product hide and republish
  - purchase approval and rejection
  - API key issue and revoke
  - user activation and suspension
- Added admin audit log screen:
  - `GET /web/admin/audit-logs`
  - search by action, target, detail, actor name, or actor email
  - filter by action
  - filter by actor user ID
  - configurable result limit up to 500
- Admin dashboard now shows audit log count and recent audit events.

## Step 23. User and Admin Notifications

Status: MVP Done

- Added `notifications` table.
- Added notification helpers:
  - create a notification for one user
  - create notifications for all active admins
  - list recent notifications
  - unread notification count
  - mark one notification as read
  - mark all notifications as read
- Notification events:
  - admins are notified when a dataset is uploaded for review
  - sellers are notified when a dataset is approved or rejected
  - admins are notified when a product purchase is requested
  - sellers are notified when their product receives a purchase request
  - buyers are notified when purchase requests are approved or rejected
- UI updates:
  - user dashboard shows recent notifications
  - admin dashboard shows recent notifications
  - top navigation shows unread notification count
  - users/admins can mark one or all notifications as read
- Cleaned Korean labels in user and admin dashboards.

## Step 24. Real-Time Upload Processing and Public Metadata Split

Status: MVP Done

- Web upload now starts a background validation job and redirects to a processing screen.
- Added processing status endpoints:
  - `GET /web/uploads/<job_id>/processing`
  - `GET /web/uploads/<job_id>/status`
- Added `dataset_processing_steps` table.
- Validation now records each processing stage:
  - file received
  - format detection and CSV normalization
  - data loading
  - duplicate check
  - schema and column statistics
  - PII detection
  - quality scoring
  - sample generation
  - report save and retention cleanup
- The customer processing screen polls status and automatically moves to the validation report when complete.
- Dataset reports now show the full processing timeline and column-level statistics.
- Market/product public views now show key safe metadata:
  - upload date
  - description
  - format
  - row and column count
  - quality score
  - column statistics preview
- PII risk and PII detection counts are hidden from public marketplace buyers.
- PII details remain visible only to dataset owner/seller and admins through report/admin-owned views.

## Step 25. Two-System Menu Structure and UI Cleanup

Status: MVP Done

- Reorganized the global navigation into two clear systems:
  - user role:
    - user data system
    - market usage system
  - admin role:
    - operations management system
    - logs and market system
- Added a cleaner topbar:
  - OBDM brand
  - common market link
  - notification shortcut with unread badge
  - logout/login actions
- Added active menu highlighting based on the current path.
- Improved header spacing, grouped menu panels, badges, status colors, and mobile wrapping.
- Cleaned corrupted Korean labels in the global navigation and footer.
- Kept page content width and dense table views suitable for an operations/product marketplace tool.

## Step 26. Dataset Hub UI Refresh

Status: MVP Done

- Rebuilt the main UI direction as an original dataset hub style inspired by:
  - search-first dataset marketplace navigation
  - resource-card browsing
  - compact tags and metadata chips
- Global UI updates:
  - cleaner OBDM brand block
  - dataset hub style top navigation
  - grouped menu panels
  - improved spacing, shadows, borders, tags, badges, buttons, and status pills
  - responsive layout for smaller screens
- Market page updates:
  - search-first filter panel
  - dataset resource card grid
  - format, quality, status, row count, column count, price, and upload date chips
  - PII fields remain hidden from public market cards
- Product detail updates:
  - dataset detail header
  - metric summary
  - column statistics table
  - sample preview table
  - sticky side metadata/action panel
  - seller/admin-only PII visibility preserved
- Upload page updates:
  - dataset upload header
  - grouped metadata/file fields
  - policy notice and action area aligned with the new visual system

## Step 27. Category and Tag Discovery

Status: MVP Done

- Added product discovery metadata:
  - `products.category`
  - `products.tags`
- Default category/tag generation:
  - CSV-like tabular data defaults to `Tabular`
  - JSON-like data defaults to `Document`
  - plain text data defaults to `Text`
  - generated tags include format, quality, and column count hints
- Existing products are backfilled with category and tag values during DB initialization.
- Product edit screen now supports category and comma-separated tags.
- Market search now supports:
  - keyword
  - category
  - tag
  - file type
  - minimum quality score
- Admin product management now supports category and tag filters.
- Market cards, product detail, and admin product tables display category/tag chips.

## Step 28. Sorting and Pagination

Status: MVP Done

- Product listing now supports pagination:
  - `page`
  - `per_page`
  - total count
  - total pages
  - previous/next page flags
- Product listing now supports sort options:
  - newest
  - oldest
  - quality high/low
  - row count high/low
  - price high/low
  - title ascending
- Market page now includes:
  - sort selector
  - page navigation
  - total result count
- Admin product management now includes:
  - sort selector
  - page size selector
  - page navigation
  - total result count
- `/products` JSON API now returns pagination metadata with product results.

## Step 29. Favorite Products

Status: MVP Done

- Added user-level favorite product storage:
  - `product_favorites`
  - unique user/product favorite rule
  - indexes for user and product lookup
- Market page now supports:
  - save product as favorite
  - remove saved favorite
  - favorite state shown on each card
- Product detail page now supports:
  - save/remove favorite action
  - favorite state beside the detail header actions
- User dashboard now includes:
  - favorite product metric
  - favorite product management table
  - direct links back to saved product detail pages
- Favorite/unfavorite actions are recorded in audit logs.

## Step 30. Smoke Test Baseline

Status: MVP Done

- Added a repeatable smoke test script:
  - `tests/smoke_test.py`
- The smoke test verifies:
  - public pages render
  - authenticated user dashboard renders
  - market search/sort page renders
  - admin dashboard and management screens render
  - product list JSON API responds
  - product detail page renders when a product exists
  - favorite save/remove flow persists correctly
- Run:

```powershell
python tests\smoke_test.py
```

## Step 31. UI Text QA Baseline

Status: MVP Done

- Added a UI text smoke test script:
  - `tests/ui_text_smoke_test.py`
- The test verifies core Korean UI labels on:
  - login
  - market
  - user dashboard
  - admin dashboard
  - admin product management
- The test also guards against old or incorrect brand remnants:
  - `All Data`
  - `Daya`
  - `brand-mark`
  - standalone `OB` logo markup
- Expanded `tests/smoke_test.py` to assert important market/dashboard phrases.
- Run:

```powershell
python tests\ui_text_smoke_test.py
```

## Step 32. Review Summary and Approval Signals

Status: MVP Done

- Added validation report review summary:
  - `review_summary.recommendation`
  - `review_summary.summary_text`
  - average NULL rate
  - high-NULL column count/list
  - PII suspicious column count/list
  - duplicate row rate
  - quality score/grade
  - structured findings with severity, title, and message
- Recommendation values:
  - `APPROVE_CANDIDATE`
  - `REVIEW_REQUIRED`
  - `REJECT_RECOMMENDED`
- Cleaned Korean progress step names/messages in the validation service.
- Rebuilt the validation report screen to show:
  - administrator approval decision summary
  - major risk findings
  - quality score components
  - PII, duplicate, schema, retention sections
- Rebuilt the admin dataset review screen to show a fast decision hint:
  - 승인 후보
  - 추가 검토
  - 반려 검토
- Added review summary test:
  - `tests/review_summary_test.py`
- Expanded UI text QA to cover the admin dataset review screen.
- Run:

```powershell
python tests\review_summary_test.py
```

## Step 33. Purchase Flow Detail and Seller Visibility

Status: MVP Done

- Added purchase request detail screen:
  - `GET /web/purchases/<request_id>`
- Purchase detail is visible to:
  - buyer
  - seller of the product
  - admin
- Purchase detail now shows:
  - request status
  - product status
  - buyer message
  - review note
  - sample download availability
  - API key issuance state
  - API usage availability
- Added seller purchase request management:
  - `GET /web/seller/purchases`
  - status filter
  - buyer name/email/company
  - product price/status
- User dashboard now shows recent purchase requests received on the seller's products.
- Admin purchase management screen was rebuilt with clean Korean UI and links to purchase detail.
- Added purchase flow test:
  - `tests/purchase_flow_test.py`
- Run:

```powershell
python tests\purchase_flow_test.py
```

## Step 34. Release Stabilization Pass 1

Status: MVP Done

- Added route and role access regression test:
  - `tests/route_access_test.py`
- Route access test verifies:
  - public pages render
  - anonymous users are redirected away from protected pages
  - regular users can access user/market/seller pages
  - regular users cannot access admin pages
  - admins can access all admin management pages
  - product detail routes respond when products exist
- Added seller purchase request shortcut to the user navigation.
- Added test execution runbook:
  - `TESTING.md`
- Stabilization test set:
  - compileall
  - smoke test
  - UI text smoke test
  - route access test
  - review summary test
  - purchase flow test
- Run:

```powershell
python tests\route_access_test.py
```

## Step 35. SQLite Schema Migration Baseline

Status: MVP Done

- Added schema migration baseline tracking:
  - `schema_migrations`
  - `SCHEMA_MIGRATIONS`
  - `list_schema_migrations`
  - `get_schema_status`
- Migration baseline versions:
  - `0001_initial_mvp`
  - `0002_marketplace_extensions`
- `init_db()` now records applied schema versions idempotently.
- Added isolated schema test using a temporary SQLite database:
  - `tests/schema_migration_test.py`
- The schema test verifies:
  - all expected tables exist
  - required extension columns exist
  - migration records exist
  - schema status is current
- Updated test runbook:
  - `TESTING.md`
- Run:

```powershell
python tests\schema_migration_test.py
```

## Step 36. Demo Seed Data

Status: MVP Done

- Added a repeatable demo seed script:
  - `data_marketplace/seed_demo.py`
- The seed script creates or reuses:
  - demo seller
  - demo buyer
  - approved dataset
  - active market product
  - approved purchase request
  - retained sample CSV
  - validation report JSON
- Demo accounts:
  - seller: `seller.demo@obdm.local`
  - buyer: `buyer.demo@obdm.local`
  - password: `demo1234`
- Added seed verification test:
  - `tests/seed_demo_test.py`
- Updated test runbook:
  - `TESTING.md`
- Run:

```powershell
python -m data_marketplace.seed_demo
python tests\seed_demo_test.py
```

## Step 37. API Key Usage Limits

Status: MVP Done

- Added API key usage limit fields:
  - `api_keys.total_request_limit`
  - `api_keys.monthly_request_limit`
- Added schema migration baseline:
  - `0003_api_key_limits`
- New API keys default to:
  - total request limit: `1000`
  - monthly request limit: `300`
- Sample API now checks limits before returning data:
  - over total limit: HTTP `429`
  - over monthly limit: HTTP `429`
- API responses now include usage summary after successful calls.
- Admin API key screen now shows:
  - monthly usage / monthly limit
  - total usage / total limit
- Added API limit test:
  - `tests/api_limit_test.py`
- Updated test runbook:
  - `TESTING.md`
- Run:

```powershell
python tests\api_limit_test.py
```

## Step 38. Sample Download Limits

Status: MVP Done

- Added purchase request sample download limit:
  - `purchase_requests.sample_download_limit`
- Added schema migration baseline:
  - `0004_sample_download_limits`
- Default buyer sample download limit:
  - `5`
- Sample download endpoint now blocks over-limit buyer downloads:
  - HTTP `429`
- Admins and sellers keep unrestricted sample access for review/management.
- Purchase detail now shows:
  - sample download limit
  - used/remaining download count
- Admin purchase detail can update sample download limit.
- User dashboard shows sample download usage for buyer requests.
- Admin purchase list shows configured sample download limit.
- Added download limit test:
  - `tests/download_limit_test.py`
- Updated test runbook:
  - `TESTING.md`
- Run:

```powershell
python tests\download_limit_test.py
```

## Step 39. Admin Operations Dashboard Enhancement

Status: MVP Done

- Expanded the admin dashboard into an operations view for OBDM.
- Added daily operating metrics:
  - today's uploads
  - today's market products
  - today's purchase requests
  - today's API calls
- Added risk summary metrics:
  - high PII dataset count
  - duplicate-risk dataset count
- Added order preparation metrics:
  - order count
  - estimated order amount
  - pending payment amount
- The admin dashboard now shows the latest order preparation list together with recent audit logs.

## Step 40. Product License And Usage Terms

Status: MVP Done

- Added product license fields:
  - `products.license_name`
  - `products.usage_terms`
- Added default usage terms for newly created market products.
- Product edit screen now lets sellers/admins update:
  - license name
  - usage terms
- Product detail screen now exposes license and usage terms to buyers before purchase.

## Step 41. Seller Revenue Estimate

Status: MVP Done

- Added seller revenue summary based on prepared orders:
  - order count
  - gross amount
  - pending amount
  - paid amount
- User dashboard now shows a seller revenue estimate panel.
- User dashboard now shows seller-side order preparation rows.

## Step 42. Order And Payment Preparation

Status: MVP Done

- Added pre-PG order table:
  - `orders`
- Approved purchase requests now generate a prepared order:
  - payment status: `PENDING`
  - order status: `CREATED`
  - currency: `KRW`
- Added order helper functions:
  - `create_order_for_purchase`
  - `list_orders`
  - `get_seller_revenue_summary`
- Added order/license verification test:
  - `tests/order_license_test.py`
- Updated schema migration verification for the order and license schema.
- Run:

```powershell
python tests\order_license_test.py
```

## Step 43. Payment Status Workflow

Status: MVP Done

- Added pre-PG payment status workflow:
  - `PENDING`
  - `PAYMENT_REQUESTED`
  - `PAID`
  - `FAILED`
  - `CANCELED`
- Added order workflow fields:
  - `orders.payment_note`
  - `orders.paid_at`
  - `orders.canceled_at`
- Added admin manual payment handling:
  - purchase detail payment status form
  - admin dashboard quick payment status action
- When an order is marked `PAID`, the linked purchase request is automatically changed to `COMPLETED`.
- Buyer and seller notifications are created when payment is confirmed.
- Added payment workflow helpers:
  - `get_order_by_purchase_request`
  - `update_order_payment_status`
- Added payment workflow test:
  - `tests/order_payment_workflow_test.py`
- Run:

```powershell
python tests\order_payment_workflow_test.py
```

## Step 44. Payment-Based Access Gate

Status: MVP Done

- Changed data access rules:
  - free products: access after purchase approval
  - paid products: access only after payment is completed
- Applied the same gate to:
  - sample download
  - API key issuance
  - API sample endpoint validation
  - purchase detail access summary
- Updated access messages so buyers can see whether they are waiting for approval or payment.
- Existing admin and seller management access remains unrestricted for review/operations.
- Added payment access gate test:
  - `tests/payment_access_gate_test.py`
- Run:

```powershell
python tests\payment_access_gate_test.py
```

## Step 45. Admin Settlement Summary

Status: MVP Done

- Added admin settlement page:
  - `/web/admin/settlements`
- Added seller settlement summary calculation:
  - seller order count
  - gross order amount
  - paid amount
  - pending amount
  - platform fee
  - settlement due amount
  - latest paid date
- Default platform fee rate:
  - `10%`
- Admins can change the fee rate on the settlement page for simulation.
- Added settlement navigation entry in the admin menu and dashboard.
- Added settlement verification test:
  - `tests/admin_settlement_test.py`
- Run:

```powershell
python tests\admin_settlement_test.py
```

## Step 47. Product Pricing Policy

Status: MVP Done

- Added product pricing model:
  - `FREE`
  - `ONE_TIME`
- Added `products.pricing_model` with automatic backfill:
  - `price <= 0` becomes `FREE`
  - `price > 0` becomes `ONE_TIME`
- Product edit screen now lets sellers/admins choose the pricing policy.
- Free products force price to `0`.
- Market and product detail screens now show the pricing policy.

## Step 48. Buyer Order And Payment History

Status: MVP Done

- Added buyer order page:
  - `/web/orders`
- Buyers can see:
  - order number
  - product name
  - pricing policy
  - amount
  - purchase status
  - payment status
  - data access readiness
  - API key status
- Added buyer order links to the user menu and dashboard.
- Added combined pricing/order verification test:
  - `tests/pricing_buyer_orders_test.py`
- Run:

```powershell
python tests\pricing_buyer_orders_test.py
```

## Step 49. Admin Operational CSV Exports

Status: MVP Done

- Added admin-only CSV export route:
  - `/web/admin/reports/<report_name>.csv`
- Supported reports:
  - `datasets`
  - `orders`
  - `settlements`
  - `api-usage`
  - `downloads`
- CSV exports are generated in memory and do not create server-side report files.
- Exports include UTF-8 BOM for spreadsheet compatibility.
- Added export links to:
  - admin dashboard
  - settlement page
  - download log page
  - API usage log page
- Added export verification test:
  - `tests/admin_csv_export_test.py`
- Run:

```powershell
python tests\admin_csv_export_test.py
```

## Step 50. Release Security Regression Pass

Status: MVP Done

- Added global security response headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: same-origin`
  - `Cache-Control: no-store`
- Hardened CSV exports against spreadsheet formula injection.
- API sample access now accepts API keys only through the `X-API-Key` header.
  - Query-string API keys are rejected to avoid leaking tokens through URLs/logs.
- Added regression coverage for:
  - anonymous and non-admin CSV export blocking
  - cross-user purchase detail blocking
  - missing CSRF rejection on web POST routes
  - CSV token hash non-exposure
  - API key hash storage
  - header-only API key usage
- Added security regression test:
  - `tests/security_regression_test.py`
- Run:

```powershell
python tests\security_regression_test.py
```

## Step 51. Full Regression Test Pass

Status: MVP Done

- Ran the full local regression suite after the security hardening pass.
- Verified the core release paths together:
  - schema migration
  - demo seed data
  - public smoke pages
  - Korean UI text QA
  - route and role access control
  - validation review summary
  - purchase flow
  - order license and terms
  - manual payment workflow
  - payment-based data access gate
  - pricing policy and buyer order history
  - sample download limits
  - API key usage limits
  - admin settlement summary
  - admin CSV exports
  - security regression checks
- Result: all regression tests passed.
- Run:

```powershell
python -m compileall app.py data_marketplace tests
python tests\schema_migration_test.py
python tests\seed_demo_test.py
python tests\smoke_test.py
python tests\ui_text_smoke_test.py
python tests\route_access_test.py
python tests\review_summary_test.py
python tests\purchase_flow_test.py
python tests\order_license_test.py
python tests\order_payment_workflow_test.py
python tests\payment_access_gate_test.py
python tests\pricing_buyer_orders_test.py
python tests\download_limit_test.py
python tests\api_limit_test.py
python tests\admin_settlement_test.py
python tests\admin_csv_export_test.py
python tests\security_regression_test.py
```

## Step 52. Upload Failure UX And Core Screen QA

Status: MVP Done

- Improved the upload processing screen for failed uploads.
- Failed upload jobs now expose customer-facing guidance through the status API:
  - `error_title`
  - `error_action`
  - original technical error kept as `error`
- Added friendly failure mapping for common upload problems:
  - unsupported file format
  - irregular CSV or delimiter parsing failure
  - invalid JSON structure
  - empty data or missing columns
- The processing page now shows:
  - clear failure summary
  - recommended next action
  - detailed cause
  - retry upload button
  - dashboard link
- The processing step table now renders dynamic values with DOM text nodes instead of direct HTML string interpolation.
- Added regression test:
  - `tests/upload_failure_ux_test.py`
- Run:

```powershell
python tests\upload_failure_ux_test.py
```

## Step 53. Admin Review Signal Enhancement

Status: MVP Done

- Enhanced the admin dataset review list with richer decision signals.
- Admin dataset rows now show:
  - review recommendation
  - average NULL rate
  - PII suspected column count
  - high-null column count
  - top review findings
  - suspected PII column names
  - high-null column names
  - key columns for quick inspection
- The admin dataset list reuses the saved validation report JSON, so PII and detailed quality signals remain visible only in seller/admin review surfaces.
- Added an admin-only approval checklist to the validation report page:
  - PII risk
  - duplicate status
  - missing-value risk
  - quality score
- Added regression test:
  - `tests/admin_review_ui_test.py`
- Run:

```powershell
python tests\admin_review_ui_test.py
```

## Step 54. Seller Dataset Progress Tracking UX

Status: MVP Done

- Improved the seller dashboard so uploaded datasets show their marketplace progress more clearly.
- Seller dataset rows now show:
  - raw dataset review status
  - seller-facing progress label
  - 4-step progress stage
  - progress bar
  - current status message
  - recommended next action
- Progress states are derived from dataset status and product publication:
  - `PASS`: automatic validation passed, waiting for admin review
  - `REVIEW`: additional review needed
  - `REJECTED`: seller action needed
  - `APPROVED`: approved, publication check needed
  - published product: visible in the market
- Seller actions now include:
  - edit before publication
  - report view
  - market product view after publication
- Added regression test:
  - `tests/seller_dataset_progress_test.py`
- Run:

```powershell
python tests\seller_dataset_progress_test.py
```

## Step 55. Rejected Dataset Resubmission Flow

Status: MVP Done

- Added rejected dataset resubmission tracking.
- Added `datasets.parent_dataset_id` so a new upload can reference the rejected source dataset.
- Sellers can now start a resubmission from:
  - seller dashboard rejected dataset row
  - rejected dataset report page
- The resubmission upload form now shows:
  - source rejected dataset
  - rejection reason
  - prefilled data name and description
  - resubmission-specific submit button
- New resubmission uploads are saved as separate datasets while keeping the parent rejected dataset link.
- API and web uploads validate that `parent_dataset_id` belongs to the current seller and is in `REJECTED` status.
- Added regression test:
  - `tests/dataset_resubmission_test.py`
- Run:

```powershell
python tests\dataset_resubmission_test.py
```

## Step 56. Dataset Resubmission History Views

Status: MVP Done

- Kept the current SQLite DBMS.
- No new DB table or field was required in this step.
- Improved seller-facing resubmission history visibility using the existing `datasets.parent_dataset_id` link.
- Seller dashboard now shows:
  - original rejected dataset link for resubmitted datasets
  - resubmission count on the source dataset
  - expandable resubmission history list
- Dataset report now shows a resubmission history section:
  - source rejected dataset link
  - source rejection reason
  - follow-up resubmission rows
  - status, quality score, and upload date for each resubmission
- Expanded regression coverage:
  - `tests/dataset_resubmission_test.py`
- Run:

```powershell
python tests\dataset_resubmission_test.py
```

## Step 57. Admin Resubmission Review Workflow

Status: MVP Done

- Improved the admin review workflow for resubmitted datasets.
- Kept the current SQLite DBMS and reused existing `datasets.parent_dataset_id`.
- Admin dataset review rows now show:
  - `보완 제출` label for resubmitted datasets
  - source rejected dataset link
  - source rejection reason
  - follow-up resubmission count
  - expandable follow-up resubmission list
  - child status and quality score
- Admins can now compare the original rejection reason and the new validation signals from the dataset list before opening the full report.
- Added regression test:
  - `tests/admin_resubmission_review_test.py`
- Run:

```powershell
python tests\admin_resubmission_review_test.py
```

## Step 58. Seller Product Operations Report

Status: MVP Done

- Added a seller-facing product operations report.
- Kept the current SQLite DBMS.
- Added product-level aggregation from existing data:
  - purchase requests
  - prepared orders
  - payment status amounts
  - sample download logs
  - API usage logs
- Added seller report route:
  - `GET /web/seller/reports`
- Seller report shows:
  - product count
  - purchase request count
  - order count
  - gross order amount
  - paid amount
  - pending amount
  - sample download count
  - API call count
  - product-level conversion and paid-rate indicators
- Added navigation from:
  - user dashboard
  - seller menu
- Added regression test:
  - `tests/seller_product_report_test.py`
- Run:

```powershell
python tests\seller_product_report_test.py
```

## Step 59. Payment Gateway Integration Preparation

Status: MVP Done

- Kept the current SQLite DBMS.
- Prepared the order/payment workflow for future PG integration while preserving the current manual admin workflow.
- Added order payment fields:
  - `orders.payment_provider`
  - `orders.payment_reference`
- Added payment event logging table:
  - `payment_events`
- Added payment service interface:
  - `data_marketplace/payments.py`
  - `request_payment`
  - `confirm_payment`
  - `fail_payment`
  - `cancel_payment`
  - `transition_payment_status`
- Admin payment status updates now pass through the payment service interface.
- Purchase detail now shows:
  - payment provider
  - payment reference
  - payment event history
- Orders CSV export now includes:
  - `payment_provider`
  - `payment_reference`
- Added regression test:
  - `tests/payment_gateway_interface_test.py`
- Run:

```powershell
python tests\payment_gateway_interface_test.py
```

## Step 60. Release Operations Checklist

Status: MVP Done

- Kept the current SQLite DBMS.
- Added deployment and operations checklist documentation:
  - `OPERATIONS_CHECKLIST.md`
- Added admin-only operations checklist screen:
  - `GET /web/admin/operations-checklist`
- The checklist summarizes:
  - `SECRET_KEY` readiness
  - admin bootstrap credential risk
  - SQLite DB path and schema migration status
  - upload, normalized CSV, sample, and report directory readiness
  - file retention policy
  - test execution baseline
  - PG integration readiness state
- Added navigation from:
  - admin global menu
  - admin dashboard action buttons
- Added regression test:
  - `tests/operations_checklist_test.py`
- Run:

```powershell
python tests\operations_checklist_test.py
```

## Step 61. Admin SQLite Backup Download

Status: MVP Done

- Kept the current SQLite DBMS.
- Added admin-only SQLite backup download route:
  - `GET /web/admin/database-backup.sqlite`
- Backup response uses a timestamped filename:
  - `obdm_sqlite_backup_YYYYMMDD_HHMMSS.sqlite`
- Added backup shortcuts from:
  - admin operations checklist
  - admin dashboard action buttons
- Updated operations documentation:
  - `OPERATIONS_CHECKLIST.md`
- Added regression test:
  - `tests/database_backup_test.py`
- Run:

```powershell
python tests\database_backup_test.py
```

## Step 62. Database Backup Audit Logging

Status: MVP Done

- Kept the current SQLite DBMS.
- Added audit logging for every admin DB backup download.
- Backup download now records:
  - action: `DATABASE_BACKUP_DOWNLOADED`
  - target type: `DATABASE`
  - generated backup filename
  - SQLite DB path
  - SQLite file size
  - requester IP through the shared audit helper
- Updated operations documentation:
  - `OPERATIONS_CHECKLIST.md`
- Expanded regression test:
  - `tests/database_backup_test.py`
- Run:

```powershell
python tests\database_backup_test.py
```

## Local Run

```powershell
cd "C:\Users\82108\OneDrive\문서\Data exchange Platform"
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000/
```
