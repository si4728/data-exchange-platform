import os
import csv
import hashlib
import json
import secrets
import threading
import uuid
from datetime import datetime
from io import StringIO
from functools import wraps
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from data_marketplace.config import (
    CONVERTED_DIR,
    DATABASE_PATH,
    DELETE_UPLOADED_FILES_AFTER_PROCESSING,
    KEEP_NORMALIZED_DATA,
    KEEP_SAMPLES,
    MAX_UPLOAD_BYTES,
    REPORT_DIR,
    SAMPLE_DIR,
    SAMPLE_SIZE,
    UPLOAD_DIR,
)
from data_marketplace.database import (
    add_product_favorite,
    count_unread_notifications,
    create_admin_notifications,
    create_notification,
    create_order_for_purchase,
    create_purchase_request,
    create_product_from_dataset,
    create_user,
    create_api_key,
    attach_processing_steps_to_dataset,
    deactivate_product_for_dataset,
    deactivate_api_key,
    get_active_api_key_for_purchase,
    get_admin_metrics,
    get_api_key,
    get_api_key_by_hash,
    get_api_key_usage_summary,
    get_dataset_report,
    get_dataset_summary,
    get_product,
    get_order_by_purchase_request,
    get_purchase_request,
    get_purchase_request_by_product_buyer,
    get_sample_download_summary,
    get_user_metrics,
    get_user_by_email,
    get_user_by_id,
    get_schema_status,
    init_db,
    is_product_favorited,
    list_datasets,
    list_datasets_by_seller,
    list_api_usage_logs,
    list_audit_logs,
    list_api_keys,
    list_access_logs,
    list_download_logs,
    list_notifications,
    list_orders,
    list_payment_events,
    list_processing_steps,
    list_favorite_product_ids,
    list_favorite_products,
    list_products_by_seller,
    list_products,
    list_purchase_requests,
    list_purchase_requests_by_buyer,
    list_purchase_requests_by_seller,
    list_seller_product_reports,
    list_seller_settlement_summaries,
    list_users,
    get_seller_revenue_summary,
    sync_approved_datasets_to_products,
    record_api_usage,
    record_access_log,
    record_audit_log,
    record_download_log,
    record_processing_step,
    mark_all_notifications_read,
    mark_notification_read,
    remove_product_favorite,
    update_purchase_request_status,
    update_product,
    update_product_status,
    update_dataset_status,
    update_purchase_download_limit,
    update_dataset_metadata,
    update_user_status,
    purchase_request_has_data_access,
    user_has_approved_purchase,
)
from data_marketplace.payments import transition_payment_status
from data_marketplace.services import validate_dataset


app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_BYTES", MAX_UPLOAD_BYTES))
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes"}

UPLOAD_JOBS: dict[str, dict] = {}
UPLOAD_JOBS_LOCK = threading.Lock()


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.context_processor
def inject_current_user():
    user = current_user()
    unread_count = count_unread_notifications(user["id"]) if user else 0
    return {
        "current_user": user,
        "csrf_token": csrf_token,
        "notification_unread_count": unread_count,
    }


@app.before_request
def validate_csrf_token():
    if request.method != "POST" or not _requires_csrf_check():
        return None

    submitted_token = request.form.get("csrf_token") or request.headers.get("X-CSRF-Token")
    if not submitted_token or submitted_token != session.get("csrf_token"):
        return render_template("not_found.html", message="요청 보안 토큰이 유효하지 않습니다."), 400
    return None


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_user_by_id(int(user_id))


def _requires_csrf_check():
    return (
        request.path in {"/login", "/register", "/logout"}
        or request.path.startswith("/web/")
    )


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if not user:
            return redirect(url_for("login"))
        if user["role"] != "ADMIN":
            return render_template("not_found.html", message="관리자 권한이 필요합니다."), 403
        return view(*args, **kwargs)

    return wrapped


@app.get("/")
def index():
    if not current_user():
        return redirect(url_for("login"))
    return render_template("upload.html", resubmit_dataset=None)


@app.get("/web/datasets/<int:dataset_id>/resubmit")
@login_required
def web_resubmit_dataset(dataset_id):
    dataset = get_dataset_summary(dataset_id)
    if dataset is None:
        return render_template("not_found.html", message="데이터셋을 찾을 수 없습니다."), 404
    if not _can_resubmit_dataset(dataset):
        return render_template("not_found.html", message="반려된 본인 데이터만 보완 재업로드할 수 있습니다."), 403
    return render_template("upload.html", resubmit_dataset=dataset)


@app.get("/register")
def register():
    return render_template("register.html")


@app.post("/register")
def register_post():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    company = request.form.get("company", "").strip()
    phone = request.form.get("phone", "").strip()

    if not name or not email or not password:
        return render_template("register.html", error="이름, 이메일, 비밀번호는 필수입니다."), 400
    if get_user_by_email(email):
        return render_template("register.html", error="이미 등록된 이메일입니다."), 400

    create_user(
        name=name,
        email=email,
        password_hash=generate_password_hash(password),
        company=company,
        phone=phone,
        role="USER",
        status="ACTIVE",
    )
    return redirect(url_for("login"))


@app.get("/login")
def login():
    return render_template("login.html")


@app.get("/policies/privacy")
def privacy_policy():
    return render_template("policy_privacy.html")


@app.get("/policies/data-retention")
def data_retention_policy():
    return render_template("policy_data_retention.html")


@app.get("/policies/seller-terms")
def seller_terms():
    return render_template("policy_seller_terms.html")


@app.post("/login")
def login_post():
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    user = get_user_by_email(email)

    if not user or not check_password_hash(user["password_hash"], password):
        _record_access(
            user["id"] if user else None,
            email,
            "LOGIN_FAIL",
            "INVALID_CREDENTIALS",
        )
        return render_template("login.html", error="이메일 또는 비밀번호가 올바르지 않습니다."), 401
    if user["status"] != "ACTIVE":
        _record_access(user["id"], email, "LOGIN_FAIL", f"ACCOUNT_{user['status']}")
        return render_template("login.html", error="활성화되지 않은 계정입니다."), 403

    session.clear()
    session["user_id"] = user["id"]
    _record_access(user["id"], user["email"], "LOGIN_SUCCESS")
    if user["role"] == "ADMIN":
        return redirect(url_for("web_admin_dashboard"))
    return redirect(url_for("user_dashboard"))


@app.post("/logout")
def logout():
    user = current_user()
    if user:
        _record_access(user["id"], user["email"], "LOGOUT")
    session.clear()
    return redirect(url_for("login"))


@app.get("/user/dashboard")
@login_required
def user_dashboard():
    user = current_user()
    datasets = _enrich_seller_dataset_progress(list_datasets_by_seller(user["id"]))
    products = list_products_by_seller(user["id"])
    purchases = list_purchase_requests_by_buyer(user["id"])
    seller_purchase_requests = list_purchase_requests_by_seller(user["id"])
    favorite_products = list_favorite_products(user["id"])
    seller_orders = list_orders(seller_id=user["id"])
    buyer_orders = list_orders(buyer_id=user["id"])
    seller_revenue = get_seller_revenue_summary(user["id"])
    new_api_token = session.pop("new_api_token", None)
    return render_template(
        "user_dashboard.html",
        datasets=datasets,
        products=products,
        purchases=purchases,
        seller_purchase_requests=seller_purchase_requests,
        favorite_products=favorite_products,
        seller_orders=seller_orders,
        buyer_orders=buyer_orders,
        seller_revenue=seller_revenue,
        metrics=get_user_metrics(user["id"]),
        notifications=list_notifications(user["id"], limit=10),
        new_api_token=new_api_token,
    )


@app.get("/web/orders")
@login_required
def web_buyer_orders():
    return render_template(
        "buyer_orders.html",
        orders=list_orders(buyer_id=current_user()["id"]),
    )


@app.get("/market")
@login_required
def market():
    filters = _get_market_filters()
    sync_approved_datasets_to_products()
    product_page = list_products(**filters, include_total=True)
    favorite_product_ids = list_favorite_product_ids(current_user()["id"])
    return render_template(
        "market.html",
        products=product_page["items"],
        pagination=product_page,
        filters=filters,
        favorite_product_ids=favorite_product_ids,
    )


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/datasets/upload")
@login_required
def upload_dataset():
    if "file" not in request.files:
        return jsonify({"status": "FAIL", "reason": "file field is required"}), 400

    if not _accepted_terms():
        return jsonify({
            "status": "FAIL",
            "reason": "data handling and deletion policy consent is required",
        }), 400

    _, resubmit_error = _get_resubmit_dataset_from_form()
    if resubmit_error:
        return jsonify({"status": "FAIL", "reason": resubmit_error}), 403

    file = request.files["file"]
    if not file.filename:
        return jsonify({"status": "FAIL", "reason": "filename is required"}), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename) or "upload.dat"
    file_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{file_id}_{safe_name}"
    file.save(upload_path)

    user_pattern = _get_user_pattern()
    job_id = str(uuid.uuid4())

    try:
        report = validate_dataset(
            upload_path,
            user_pattern=user_pattern,
            metadata=_get_dataset_metadata(),
            progress_callback=_build_progress_recorder(job_id),
        )
        attach_processing_steps_to_dataset(job_id, report["dataset_id"])
    except Exception as exc:
        if Path(upload_path).exists():
            Path(upload_path).unlink()
        return jsonify({"status": "FAIL", "reason": str(exc)}), 400

    _notify_admins(
        "DATASET_REVIEW",
        "새 데이터 검토 요청",
        f"{report['metadata']['data_name']} 데이터가 업로드되었습니다.",
        "DATASET",
        report["dataset_id"],
    )
    report["processing_steps"] = list_processing_steps(job_id=job_id)
    return jsonify(report), 201


@app.post("/web/datasets/upload")
@login_required
def web_upload_dataset():
    resubmit_dataset, resubmit_error = _get_resubmit_dataset_from_form()
    if resubmit_error:
        return render_template("not_found.html", message=resubmit_error), 403

    if not _accepted_terms():
        return render_template(
            "upload.html",
            error="데이터 처리, 샘플 보관, 원본 삭제 정책에 동의해야 업로드할 수 있습니다.",
            resubmit_dataset=resubmit_dataset,
        ), 400

    if "file" not in request.files:
        return render_template("upload.html", error="파일을 선택해 주세요.", resubmit_dataset=resubmit_dataset), 400

    file = request.files["file"]
    if not file.filename:
        return render_template("upload.html", error="파일명이 비어 있습니다.", resubmit_dataset=resubmit_dataset), 400

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename) or "upload.dat"
    file_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{file_id}_{safe_name}"
    file.save(upload_path)
    job_id = str(uuid.uuid4())
    _start_upload_job(
        job_id=job_id,
        upload_path=upload_path,
        user_pattern=_get_user_pattern(),
        metadata=_get_dataset_metadata(),
    )
    return redirect(url_for("web_upload_processing", job_id=job_id))


@app.get("/web/uploads/<job_id>/processing")
@login_required
def web_upload_processing(job_id):
    job = _get_upload_job(job_id)
    if not job or not _can_view_upload_job(job):
        return render_template("not_found.html", message="업로드 작업을 찾을 수 없습니다."), 404
    return render_template("upload_processing.html", job_id=job_id, job=job)


@app.get("/web/uploads/<job_id>/status")
@login_required
def web_upload_status(job_id):
    job = _get_upload_job(job_id)
    if not job or not _can_view_upload_job(job):
        return jsonify({"status": "FAIL", "reason": "upload job not found"}), 404

    error_info = _upload_error_info(job.get("error"))
    return jsonify({
        "job_id": job_id,
        "status": job["status"],
        "dataset_id": job.get("dataset_id"),
        "report_url": url_for("web_dataset_report", dataset_id=job["dataset_id"]) if job.get("dataset_id") else None,
        "error": job.get("error"),
        "error_title": error_info["title"],
        "error_action": error_info["action"],
        "steps": list_processing_steps(job_id=job_id),
    })


@app.get("/web/datasets/<int:dataset_id>")
@login_required
def web_dataset_report(dataset_id):
    report = get_dataset_report(dataset_id)
    if report is None:
        return render_template("not_found.html", message="데이터셋을 찾을 수 없습니다."), 404
    dataset = get_dataset_summary(dataset_id)
    if dataset:
        report["review_note"] = dataset.get("review_note")
        report["dataset_status"] = dataset.get("status")
        report["parent_dataset_id"] = dataset.get("parent_dataset_id")

    if not _can_view_dataset(report):
        return render_template("not_found.html", message="데이터셋 접근 권한이 없습니다."), 403

    resubmission_context = _dataset_resubmission_context(dataset) if dataset else {}

    return render_template(
        "report.html",
        report=report,
        processing_steps=list_processing_steps(dataset_id=dataset_id),
        resubmission_context=resubmission_context,
    )


@app.get("/web/datasets/<int:dataset_id>/edit")
@login_required
def web_edit_dataset(dataset_id):
    dataset = get_dataset_summary(dataset_id)
    if dataset is None:
        return render_template("not_found.html", message="데이터셋을 찾을 수 없습니다."), 404
    if not _can_edit_dataset(dataset):
        return render_template("not_found.html", message="게시 전 본인 데이터만 수정할 수 있습니다."), 403

    return render_template("dataset_edit.html", dataset=dataset)


@app.post("/web/datasets/<int:dataset_id>/edit")
@login_required
def web_update_dataset(dataset_id):
    dataset = get_dataset_summary(dataset_id)
    if dataset is None:
        return render_template("not_found.html", message="데이터셋을 찾을 수 없습니다."), 404
    if not _can_edit_dataset(dataset):
        return render_template("not_found.html", message="게시 전 본인 데이터만 수정할 수 있습니다."), 403

    data_name = request.form.get("data_name", "").strip()
    description = request.form.get("description", "").strip()
    if not data_name:
        return render_template("dataset_edit.html", dataset=dataset, error="데이터 이름은 필수입니다."), 400

    update_dataset_metadata(dataset_id, data_name, description)
    return redirect(url_for("web_dataset_report", dataset_id=dataset_id))


@app.get("/web/admin/datasets")
@admin_required
def web_admin_list_datasets():
    filters = _get_admin_dataset_filters()
    datasets = _enrich_admin_review_datasets(list_datasets(**filters))
    return render_template(
        "admin_datasets.html",
        datasets=datasets,
        filters=filters,
    )


@app.get("/web/admin")
@admin_required
def web_admin_dashboard():
    return render_template(
        "admin_dashboard.html",
        users=list_users(),
        datasets=list_datasets(),
        purchases=list_purchase_requests(),
        download_logs=list_download_logs(),
        api_usage_logs=list_api_usage_logs(),
        orders=list_orders(),
        audit_logs=list_audit_logs(limit=10),
        notifications=list_notifications(current_user()["id"], limit=10),
        metrics=get_admin_metrics(),
    )


@app.get("/web/admin/operations-checklist")
@admin_required
def web_admin_operations_checklist():
    return render_template(
        "admin_operations_checklist.html",
        operations_status=_build_operations_checklist_status(),
    )


@app.get("/web/admin/database-backup.sqlite")
@admin_required
def web_admin_database_backup():
    init_db()
    if not DATABASE_PATH.exists():
        return render_template("not_found.html", message="DB 파일을 찾을 수 없습니다."), 404

    filename = f"obdm_sqlite_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite"
    _record_audit(
        "DATABASE_BACKUP_DOWNLOADED",
        "DATABASE",
        detail={
            "filename": filename,
            "database_path": str(DATABASE_PATH),
            "file_size_bytes": DATABASE_PATH.stat().st_size,
        },
    )
    return Response(
        DATABASE_PATH.read_bytes(),
        mimetype="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/web/admin/users")
@admin_required
def web_admin_users():
    filters = _get_admin_user_filters()
    users = list_users(**filters)
    totals = {
        "total": len(users),
        "active": sum(1 for user in users if user["status"] == "ACTIVE"),
        "suspended": sum(1 for user in users if user["status"] == "SUSPENDED"),
        "admin": sum(1 for user in users if user["role"] == "ADMIN"),
    }
    return render_template("admin_users.html", users=users, filters=filters, totals=totals)


@app.get("/web/admin/products")
@admin_required
def web_admin_products():
    filters = _get_admin_product_filters()
    product_page = list_products(**filters, include_total=True)
    return render_template(
        "admin_products.html",
        products=product_page["items"],
        pagination=product_page,
        filters=filters,
    )


@app.get("/web/admin/settlements")
@admin_required
def web_admin_settlements():
    fee_rate = _parse_float_arg("fee_rate")
    if fee_rate is None:
        fee_rate = 0.1
    if fee_rate > 1:
        fee_rate = fee_rate / 100
    fee_rate = max(0.0, min(float(fee_rate), 1.0))
    settlements = list_seller_settlement_summaries(fee_rate=fee_rate)
    totals = {
        "seller_count": len(settlements),
        "order_count": sum(int(item["order_count"] or 0) for item in settlements),
        "gross_amount": sum(int(item["gross_amount"] or 0) for item in settlements),
        "paid_amount": sum(int(item["paid_amount"] or 0) for item in settlements),
        "pending_amount": sum(int(item["pending_amount"] or 0) for item in settlements),
        "platform_fee": sum(int(item["platform_fee"] or 0) for item in settlements),
        "settlement_due_amount": sum(int(item["settlement_due_amount"] or 0) for item in settlements),
    }
    return render_template(
        "admin_settlements.html",
        settlements=settlements,
        totals=totals,
        fee_rate=fee_rate,
    )


@app.get("/web/admin/reports/<report_name>.csv")
@admin_required
def web_admin_export_report(report_name):
    fee_rate = _parse_float_arg("fee_rate")
    if fee_rate is None:
        fee_rate = 0.1
    if fee_rate > 1:
        fee_rate = fee_rate / 100

    reports = _admin_report_definitions(max(0.0, min(float(fee_rate), 1.0)))
    if report_name not in reports:
        return render_template("not_found.html", message="지원하지 않는 리포트입니다."), 404

    report = reports[report_name]
    return _csv_response(report["filename"], report["rows"], report["columns"])


@app.post("/web/admin/users/<int:user_id>/activate")
@admin_required
def web_admin_activate_user(user_id):
    if update_user_status(user_id, "ACTIVE"):
        _record_audit("USER_ACTIVATED", "USER", user_id, {"status": "ACTIVE"})
    return redirect(url_for("web_admin_users"))


@app.post("/web/admin/users/<int:user_id>/suspend")
@admin_required
def web_admin_suspend_user(user_id):
    if user_id == current_user()["id"]:
        return render_template("not_found.html", message="본인 계정은 정지할 수 없습니다."), 400
    if update_user_status(user_id, "SUSPENDED"):
        _record_audit("USER_SUSPENDED", "USER", user_id, {"status": "SUSPENDED"})
    return redirect(url_for("web_admin_users"))


@app.post("/web/admin/datasets/<int:dataset_id>/approve")
@admin_required
def web_admin_approve_dataset(dataset_id):
    if update_dataset_status(dataset_id, "APPROVED", ""):
        create_product_from_dataset(dataset_id)
        _record_audit("DATASET_APPROVED", "DATASET", dataset_id, {"status": "APPROVED"})
        dataset = get_dataset_summary(dataset_id)
        if dataset:
            _notify_user(
                dataset["seller_id"],
                "DATASET_APPROVED",
                "데이터가 승인되었습니다",
                f"{dataset.get('data_name') or dataset.get('filename')} 데이터가 마켓에 게시되었습니다.",
                "DATASET",
                dataset_id,
            )
    return redirect(url_for("web_admin_list_datasets"))


@app.post("/web/admin/datasets/<int:dataset_id>/reject")
@admin_required
def web_admin_reject_dataset(dataset_id):
    review_note = request.form.get("review_note", "").strip()
    if update_dataset_status(dataset_id, "REJECTED", review_note):
        deactivate_product_for_dataset(dataset_id)
        _record_audit("DATASET_REJECTED", "DATASET", dataset_id, {"review_note": review_note})
        dataset = get_dataset_summary(dataset_id)
        if dataset:
            message = f"{dataset.get('data_name') or dataset.get('filename')} 데이터가 반려되었습니다."
            if review_note:
                message += f" 사유: {review_note}"
            _notify_user(
                dataset["seller_id"],
                "DATASET_REJECTED",
                "데이터가 반려되었습니다",
                message,
                "DATASET",
                dataset_id,
            )
    return redirect(url_for("web_admin_list_datasets"))


@app.post("/web/admin/datasets/<int:dataset_id>/publish")
@admin_required
def web_admin_publish_dataset(dataset_id):
    try:
        product = create_product_from_dataset(dataset_id)
    except ValueError as exc:
        return render_template("not_found.html", message=str(exc)), 400

    _record_audit("DATASET_PUBLISHED", "DATASET", dataset_id, {"product_id": product["id"]})
    return redirect(url_for("market"))


@app.get("/web/products/<int:product_id>")
@login_required
def web_product_detail(product_id):
    product = get_product(product_id, include_inactive=True)
    if product is None:
        return render_template("not_found.html", message="상품을 찾을 수 없습니다."), 404
    if product["status"] != "ACTIVE" and not _can_manage_product(product):
        return render_template("not_found.html", message="비공개 상품입니다."), 404

    sample_preview = _load_sample_preview(product)
    purchase_request = _get_current_purchase_request(product_id)
    can_download_sample = _can_access_product_file(product)
    is_favorite = is_product_favorited(product_id, current_user()["id"])
    return render_template(
        "product_detail.html",
        product=product,
        sample_preview=sample_preview,
        purchase_request=purchase_request,
        can_download_sample=can_download_sample,
        can_view_sensitive=_can_manage_product(product),
        is_favorite=is_favorite,
    )


@app.get("/web/products/<int:product_id>/edit")
@login_required
def web_edit_product(product_id):
    product = get_product(product_id, include_inactive=True)
    if product is None:
        return render_template("not_found.html", message="상품을 찾을 수 없습니다."), 404
    if not _can_manage_product(product):
        return render_template("not_found.html", message="상품 수정 권한이 없습니다."), 403

    return render_template("product_edit.html", product=product)


@app.post("/web/products/<int:product_id>/edit")
@login_required
def web_update_product(product_id):
    product = get_product(product_id, include_inactive=True)
    if product is None:
        return render_template("not_found.html", message="상품을 찾을 수 없습니다."), 404
    if not _can_manage_product(product):
        return render_template("not_found.html", message="상품 수정 권한이 없습니다."), 403

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "").strip()
    tags = request.form.get("tags", "").strip()
    pricing_model = request.form.get("pricing_model", "ONE_TIME").strip().upper()
    license_name = request.form.get("license_name", "").strip()
    usage_terms = request.form.get("usage_terms", "").strip()
    price = _parse_int_form("price", default=0)
    if pricing_model == "FREE":
        price = 0
    if pricing_model not in {"FREE", "ONE_TIME"}:
        pricing_model = "ONE_TIME"
    if not title:
        return render_template("product_edit.html", product=product, error="상품명은 필수입니다."), 400
    if price < 0:
        return render_template("product_edit.html", product=product, error="가격은 0 이상이어야 합니다."), 400

    if update_product(product_id, title, description, price, category, tags, license_name, usage_terms, pricing_model):
        _record_audit(
            "PRODUCT_UPDATED",
            "PRODUCT",
            product_id,
            {
                "title": title,
                "price": price,
                "category": category,
                "tags": tags,
                "license_name": license_name,
                "pricing_model": pricing_model,
            },
        )
    return redirect(url_for("web_product_detail", product_id=product_id))


@app.post("/web/products/<int:product_id>/hide")
@login_required
def web_hide_product(product_id):
    product = get_product(product_id, include_inactive=True)
    if product is None:
        return render_template("not_found.html", message="상품을 찾을 수 없습니다."), 404
    if not _can_manage_product(product):
        return render_template("not_found.html", message="상품 상태 변경 권한이 없습니다."), 403

    if update_product_status(product_id, "INACTIVE"):
        _record_audit("PRODUCT_HIDDEN", "PRODUCT", product_id, {"status": "INACTIVE"})
    return redirect(url_for("user_dashboard") if current_user()["role"] != "ADMIN" else url_for("web_admin_dashboard"))


@app.post("/web/products/<int:product_id>/publish")
@login_required
def web_publish_product(product_id):
    product = get_product(product_id, include_inactive=True)
    if product is None:
        return render_template("not_found.html", message="상품을 찾을 수 없습니다."), 404
    if not _can_manage_product(product):
        return render_template("not_found.html", message="상품 상태 변경 권한이 없습니다."), 403

    if update_product_status(product_id, "ACTIVE"):
        _record_audit("PRODUCT_PUBLISHED", "PRODUCT", product_id, {"status": "ACTIVE"})
    return redirect(url_for("web_product_detail", product_id=product_id))


@app.post("/web/products/<int:product_id>/purchase")
@login_required
def web_purchase_product(product_id):
    product = get_product(product_id)
    if product is None:
        return render_template("not_found.html", message="상품을 찾을 수 없습니다."), 404
    if product.get("seller_id") == current_user()["id"]:
        return render_template("not_found.html", message="본인이 등록한 데이터는 구매 요청할 수 없습니다."), 400

    purchase = create_purchase_request(
        product_id=product_id,
        buyer_id=current_user()["id"],
        message=request.form.get("message", ""),
    )
    _notify_admins(
        "PURCHASE_REQUESTED",
        "새 구매 요청",
        f"{current_user()['name']} 사용자가 {product['title']} 상품 구매를 요청했습니다.",
        "PURCHASE_REQUEST",
        purchase["id"],
    )
    _notify_user(
        product["seller_id"],
        "PURCHASE_REQUESTED",
        "내 상품에 구매 요청이 들어왔습니다",
        f"{product['title']} 상품에 새 구매 요청이 들어왔습니다.",
        "PURCHASE_REQUEST",
        purchase["id"],
    )
    return redirect(url_for("user_dashboard"))


@app.post("/web/products/<int:product_id>/favorite")
@login_required
def web_add_product_favorite(product_id):
    product = get_product(product_id)
    if product is None:
        return render_template("not_found.html", message="상품을 찾을 수 없습니다."), 404

    add_product_favorite(product_id, current_user()["id"])
    _record_audit("PRODUCT_FAVORITED", "PRODUCT", product_id, {"title": product["title"]})
    return redirect(request.form.get("next") or request.referrer or url_for("market"))


@app.post("/web/products/<int:product_id>/favorite/delete")
@login_required
def web_remove_product_favorite(product_id):
    remove_product_favorite(product_id, current_user()["id"])
    _record_audit("PRODUCT_UNFAVORITED", "PRODUCT", product_id, {})
    return redirect(request.form.get("next") or request.referrer or url_for("market"))


@app.get("/web/admin/purchases")
@admin_required
def web_admin_purchases():
    filters = _get_purchase_filters()
    return render_template(
        "admin_purchases.html",
        purchases=list_purchase_requests(**filters),
        filters=filters,
    )


@app.get("/web/seller/purchases")
@login_required
def web_seller_purchases():
    selected_status = request.args.get("status", "").strip() or None
    return render_template(
        "seller_purchases.html",
        purchases=list_purchase_requests_by_seller(current_user()["id"], status=selected_status),
        selected_status=selected_status,
    )


@app.get("/web/seller/reports")
@login_required
def web_seller_reports():
    reports = list_seller_product_reports(current_user()["id"])
    totals = {
        "product_count": len(reports),
        "purchase_request_count": sum(int(item["purchase_request_count"] or 0) for item in reports),
        "order_count": sum(int(item["order_count"] or 0) for item in reports),
        "gross_amount": sum(int(item["gross_amount"] or 0) for item in reports),
        "paid_amount": sum(int(item["paid_amount"] or 0) for item in reports),
        "pending_amount": sum(int(item["pending_amount"] or 0) for item in reports),
        "sample_download_count": sum(int(item["sample_download_count"] or 0) for item in reports),
        "api_usage_count": sum(int(item["api_usage_count"] or 0) for item in reports),
    }
    return render_template("seller_reports.html", reports=reports, totals=totals)


@app.get("/web/purchases/<int:request_id>")
@login_required
def web_purchase_detail(request_id):
    purchase = get_purchase_request(request_id)
    if purchase is None:
        return render_template("not_found.html", message="구매 요청을 찾을 수 없습니다."), 404
    if not _can_view_purchase_request(purchase):
        return render_template("not_found.html", message="구매 요청을 볼 권한이 없습니다."), 403

    product = get_product(purchase["product_id"], include_inactive=True)
    api_key = get_active_api_key_for_purchase(request_id) if purchase["buyer_id"] == current_user()["id"] else None
    order = get_order_by_purchase_request(request_id)
    access = _purchase_access_summary(purchase, api_key, order)
    payment_events = list_payment_events(order["id"]) if order else []
    return render_template(
        "purchase_detail.html",
        purchase=purchase,
        product=product,
        api_key=api_key,
        access=access,
        order=order,
        payment_events=payment_events,
    )


@app.get("/web/admin/downloads")
@admin_required
def web_admin_downloads():
    return render_template("admin_downloads.html", download_logs=list_download_logs())


@app.get("/web/admin/api-usage")
@admin_required
def web_admin_api_usage():
    return render_template("admin_api_usage.html", api_usage_logs=list_api_usage_logs())


@app.get("/web/admin/audit-logs")
@admin_required
def web_admin_audit_logs():
    filters = _get_audit_log_filters()
    return render_template(
        "admin_audit_logs.html",
        audit_logs=list_audit_logs(**filters),
        filters=filters,
    )


@app.get("/web/admin/access-logs")
@admin_required
def web_admin_access_logs():
    filters = _get_access_log_filters()
    return render_template(
        "admin_access_logs.html",
        access_logs=list_access_logs(**filters),
        filters=filters,
    )


@app.post("/web/notifications/<int:notification_id>/read")
@login_required
def web_mark_notification_read(notification_id):
    mark_notification_read(notification_id, current_user()["id"])
    next_url = request.form.get("next") or request.referrer or url_for("user_dashboard")
    return redirect(next_url)


@app.post("/web/notifications/read-all")
@login_required
def web_mark_all_notifications_read():
    mark_all_notifications_read(current_user()["id"])
    next_url = request.form.get("next") or request.referrer or url_for("user_dashboard")
    return redirect(next_url)


@app.get("/web/admin/api-keys")
@admin_required
def web_admin_api_keys():
    status = request.args.get("status", "").strip() or None
    return render_template(
        "admin_api_keys.html",
        api_keys=list_api_keys(status=status),
        selected_status=status,
    )


@app.post("/web/admin/purchases/<int:request_id>/approve")
@admin_required
def web_admin_approve_purchase(request_id):
    if update_purchase_request_status(request_id, "APPROVED", ""):
        order = create_order_for_purchase(request_id)
        _record_audit("PURCHASE_APPROVED", "PURCHASE_REQUEST", request_id, {"status": "APPROVED"})
        purchase = get_purchase_request(request_id)
        if purchase:
            _notify_user(
                purchase["buyer_id"],
                "PURCHASE_APPROVED",
                "구매 요청이 승인되었습니다",
                f"{purchase['product_title']} 상품 구매 요청이 승인되었습니다. 이제 샘플/API를 사용할 수 있습니다.",
                "PURCHASE_REQUEST",
                request_id,
            )
            if order:
                _record_audit("ORDER_CREATED", "ORDER", order["id"], {"purchase_request_id": request_id})
    return redirect(url_for("web_admin_purchases"))


@app.post("/web/admin/purchases/<int:request_id>/reject")
@admin_required
def web_admin_reject_purchase(request_id):
    review_note = request.form.get("review_note", "").strip()
    if update_purchase_request_status(request_id, "REJECTED", review_note):
        _record_audit("PURCHASE_REJECTED", "PURCHASE_REQUEST", request_id, {"review_note": review_note})
        purchase = get_purchase_request(request_id)
        if purchase:
            message = f"{purchase['product_title']} 상품 구매 요청이 반려되었습니다."
            if review_note:
                message += f" 사유: {review_note}"
            _notify_user(
                purchase["buyer_id"],
                "PURCHASE_REJECTED",
                "구매 요청이 반려되었습니다",
                message,
                "PURCHASE_REQUEST",
                request_id,
            )
    return redirect(url_for("web_admin_purchases"))


@app.post("/web/admin/purchases/<int:request_id>/download-limit")
@admin_required
def web_admin_update_purchase_download_limit(request_id):
    sample_download_limit = _parse_int_form("sample_download_limit", default=5)
    if update_purchase_download_limit(request_id, sample_download_limit):
        _record_audit(
            "PURCHASE_DOWNLOAD_LIMIT_UPDATED",
            "PURCHASE_REQUEST",
            request_id,
            {"sample_download_limit": sample_download_limit},
        )
    return redirect(request.referrer or url_for("web_admin_purchases"))


@app.post("/web/admin/orders/<int:order_id>/payment-status")
@admin_required
def web_admin_update_order_payment_status(order_id):
    payment_status = request.form.get("payment_status", "").strip().upper()
    payment_note = request.form.get("payment_note", "").strip()
    payment_provider = request.form.get("payment_provider", "MANUAL").strip() or "MANUAL"
    payment_reference = request.form.get("payment_reference", "").strip()
    try:
        order = transition_payment_status(
            order_id,
            payment_status,
            note=payment_note,
            provider=payment_provider,
            provider_reference=payment_reference,
            detail={"actor": "ADMIN_MANUAL_UPDATE"},
        )
    except ValueError as exc:
        return render_template("not_found.html", message=str(exc)), 400

    if order is None:
        return render_template("not_found.html", message="주문을 찾을 수 없습니다."), 404

    _record_audit(
        "ORDER_PAYMENT_STATUS_UPDATED",
        "ORDER",
        order_id,
        {
            "payment_status": order["payment_status"],
            "order_status": order["order_status"],
            "purchase_request_id": order["purchase_request_id"],
        },
    )
    if order["payment_status"] == "PAID":
        _notify_user(
            order["buyer_id"],
            "PAYMENT_CONFIRMED",
            "결제가 완료되었습니다",
            f"{order['product_title']} 상품 결제가 완료되어 구매 상태가 완료로 변경되었습니다.",
            "ORDER",
            order_id,
        )
        _notify_user(
            order["seller_id"],
            "PAYMENT_CONFIRMED",
            "판매 주문 결제가 완료되었습니다",
            f"{order['product_title']} 상품 주문 결제가 완료되었습니다.",
            "ORDER",
            order_id,
        )

    return redirect(request.form.get("next") or request.referrer or url_for("web_admin_dashboard"))


@app.post("/web/purchases/<int:request_id>/api-key")
@login_required
def web_issue_api_key(request_id):
    purchase = get_purchase_request_by_id_for_current_user(request_id)
    if purchase is None:
        return render_template("not_found.html", message="구매 요청을 찾을 수 없습니다."), 404
    if not purchase_request_has_data_access(request_id):
        return render_template("not_found.html", message="유료 상품은 결제 완료 후 API 키를 발급할 수 있습니다."), 400
    if get_active_api_key_for_purchase(request_id):
        return redirect(url_for("user_dashboard"))

    token = f"ad_{secrets.token_urlsafe(32)}"
    api_key = create_api_key(
        purchase_request_id=request_id,
        token_hash=_hash_token(token),
        token_prefix=token[:12],
    )
    _record_audit("API_KEY_ISSUED", "API_KEY", api_key["id"], {"purchase_request_id": request_id})
    session["new_api_token"] = token
    return redirect(url_for("user_dashboard"))


@app.post("/web/api-keys/<int:api_key_id>/revoke")
@login_required
def web_revoke_api_key(api_key_id):
    api_key = get_api_key(api_key_id)
    user = current_user()
    if api_key is None:
        return render_template("not_found.html", message="API 키를 찾을 수 없습니다."), 404
    if user["role"] != "ADMIN" and api_key["user_id"] != user["id"]:
        return render_template("not_found.html", message="API 키 관리 권한이 없습니다."), 403

    if deactivate_api_key(api_key_id, None if user["role"] == "ADMIN" else user["id"]):
        _record_audit("API_KEY_REVOKED", "API_KEY", api_key_id, {"role": user["role"]})
    if user["role"] == "ADMIN":
        return redirect(url_for("web_admin_api_keys"))
    return redirect(url_for("user_dashboard"))


@app.get("/admin/datasets")
@admin_required
def admin_list_datasets():
    filters = _get_admin_dataset_filters()
    return jsonify({
        "datasets": list_datasets(**filters),
        "filters": filters,
    })


@app.get("/admin/datasets/<int:dataset_id>")
@admin_required
def admin_get_dataset(dataset_id):
    report = get_dataset_report(dataset_id)
    if report is None:
        return jsonify({"status": "FAIL", "reason": "dataset not found"}), 404

    return jsonify(report)


@app.post("/admin/datasets/<int:dataset_id>/approve")
@admin_required
def admin_approve_dataset(dataset_id):
    if not update_dataset_status(dataset_id, "APPROVED", ""):
        return jsonify({"status": "FAIL", "reason": "dataset not found"}), 404
    product = create_product_from_dataset(dataset_id)
    _record_audit("DATASET_APPROVED", "DATASET", dataset_id, {"product_id": product["id"]})
    dataset = get_dataset_summary(dataset_id)
    if dataset:
        _notify_user(
            dataset["seller_id"],
            "DATASET_APPROVED",
            "데이터가 승인되었습니다",
            f"{dataset.get('data_name') or dataset.get('filename')} 데이터가 마켓에 게시되었습니다.",
            "DATASET",
            dataset_id,
        )

    return jsonify({"status": "APPROVED", "dataset_id": dataset_id, "product": product})


@app.post("/admin/datasets/<int:dataset_id>/reject")
@admin_required
def admin_reject_dataset(dataset_id):
    payload = request.get_json(silent=True) or {}
    if not update_dataset_status(dataset_id, "REJECTED", payload.get("review_note", "")):
        return jsonify({"status": "FAIL", "reason": "dataset not found"}), 404
    deactivate_product_for_dataset(dataset_id)
    _record_audit("DATASET_REJECTED", "DATASET", dataset_id, {"review_note": payload.get("review_note", "")})
    dataset = get_dataset_summary(dataset_id)
    if dataset:
        _notify_user(
            dataset["seller_id"],
            "DATASET_REJECTED",
            "데이터가 반려되었습니다",
            f"{dataset.get('data_name') or dataset.get('filename')} 데이터가 반려되었습니다.",
            "DATASET",
            dataset_id,
        )

    return jsonify({"status": "REJECTED", "dataset_id": dataset_id})


@app.post("/admin/datasets/<int:dataset_id>/publish")
@admin_required
def admin_publish_dataset(dataset_id):
    payload = request.get_json(silent=True) or {}

    try:
        product = create_product_from_dataset(
            dataset_id,
            title=payload.get("title"),
            description=payload.get("description"),
            price=payload.get("price", 0),
        )
    except ValueError as exc:
        return jsonify({"status": "FAIL", "reason": str(exc)}), 400

    _record_audit("DATASET_PUBLISHED", "DATASET", dataset_id, {"product_id": product["id"]})
    return jsonify({"status": "PUBLISHED", "product": product}), 201


@app.get("/products")
@login_required
def product_list():
    filters = _get_market_filters()
    sync_approved_datasets_to_products()
    product_page = list_products(**filters, include_total=True)
    return jsonify({
        "products": product_page["items"],
        "pagination": {
            "total": product_page["total"],
            "page": product_page["page"],
            "per_page": product_page["per_page"],
            "total_pages": product_page["total_pages"],
            "has_prev": product_page["has_prev"],
            "has_next": product_page["has_next"],
        },
        "filters": filters,
    })


@app.get("/products/<int:product_id>")
@login_required
def product_detail(product_id):
    product = get_product(product_id)
    if product is None:
        return jsonify({"status": "FAIL", "reason": "product not found"}), 404

    return jsonify(product)


@app.get("/products/<int:product_id>/sample")
@login_required
def product_sample(product_id):
    product = get_product(product_id)
    if product is None:
        return jsonify({"status": "FAIL", "reason": "product not found"}), 404
    if not _can_access_product_file(product):
        return jsonify({"status": "FAIL", "reason": "payment completion is required for paid products"}), 403
    download_summary = _sample_download_limit_summary(product)
    if download_summary and download_summary["is_exceeded"]:
        return jsonify({
            "status": "FAIL",
            "reason": download_summary["reason"],
            "download": download_summary,
        }), 429

    sample_path = _get_sample_path(product)
    if sample_path is None or not sample_path.exists():
        return jsonify({"status": "FAIL", "reason": "sample not found"}), 404

    record_download_log(
        product_id=product["id"],
        user_id=current_user()["id"],
        file_name=sample_path.name,
        ip_address=request.remote_addr or "",
    )
    return send_file(sample_path, as_attachment=True, download_name=sample_path.name)


@app.get("/api/v1/products/<int:product_id>/sample")
def api_product_sample(product_id):
    api_key = _get_valid_api_key(product_id)
    if api_key is None:
        return jsonify({"status": "FAIL", "reason": "valid API key is required"}), 401
    usage_summary = get_api_key_usage_summary(api_key["id"])
    if usage_summary["is_exceeded"]:
        return jsonify({
            "status": "FAIL",
            "reason": usage_summary["reason"],
            "usage": usage_summary,
        }), 429

    product = get_product(product_id)
    if product is None:
        return jsonify({"status": "FAIL", "reason": "product not found"}), 404

    limit = int(_parse_float_arg("limit") or 20)
    limit = max(1, min(limit, 100))
    sample_preview = _load_sample_preview(product, limit=limit)
    record_api_usage(
        api_key_id=api_key["id"],
        product_id=product_id,
        user_id=api_key["user_id"],
        endpoint=request.path,
        ip_address=request.remote_addr or "",
    )
    return jsonify({
        "status": "OK",
        "product_id": product_id,
        "title": product["title"],
        "columns": sample_preview["columns"],
        "rows": sample_preview["rows"],
        "limit": limit,
        "usage": get_api_key_usage_summary(api_key["id"]),
    })


def _get_user_pattern():
    file_format = request.form.get("format")
    delimiter = request.form.get("delimiter")

    if not file_format:
        return None

    return {
        "file_format": file_format,
        "delimiter": delimiter,
    }


def _get_market_filters():
    return {
        "query": request.args.get("q", "").strip(),
        "category": request.args.get("category", "").strip() or None,
        "tag": request.args.get("tag", "").strip() or None,
        "file_type": request.args.get("file_type", "").strip() or None,
        "min_quality_score": _parse_float_arg("min_quality_score"),
        "max_pii_risk_score": None,
        "status": "ACTIVE",
        "sort": request.args.get("sort", "newest").strip() or "newest",
        "page": _parse_int_arg("page", default=1) or 1,
        "per_page": _parse_int_arg("per_page", default=12) or 12,
    }


def _get_admin_product_filters():
    status = request.args.get("status", "").strip()
    return {
        "query": request.args.get("q", "").strip(),
        "category": request.args.get("category", "").strip() or None,
        "tag": request.args.get("tag", "").strip() or None,
        "file_type": request.args.get("file_type", "").strip() or None,
        "min_quality_score": _parse_float_arg("min_quality_score"),
        "max_pii_risk_score": _parse_float_arg("max_pii_risk_score"),
        "status": status or None,
        "sort": request.args.get("sort", "newest").strip() or "newest",
        "page": _parse_int_arg("page", default=1) or 1,
        "per_page": _parse_int_arg("per_page", default=20) or 20,
    }


def _get_admin_dataset_filters():
    return {
        "query": request.args.get("q", "").strip(),
        "status": request.args.get("status", "").strip() or None,
        "duplicate_status": request.args.get("duplicate_status", "").strip() or None,
        "min_quality_score": _parse_float_arg("min_quality_score"),
        "max_quality_score": _parse_float_arg("max_quality_score"),
        "min_pii_risk_score": _parse_float_arg("min_pii_risk_score"),
        "max_pii_risk_score": _parse_float_arg("max_pii_risk_score"),
    }


def _get_admin_user_filters():
    return {
        "query": request.args.get("q", "").strip(),
        "role": request.args.get("role", "").strip() or None,
        "status": request.args.get("status", "").strip() or None,
        "limit": _parse_int_arg("limit", default=500) or 500,
    }


def _enrich_admin_review_datasets(datasets):
    all_datasets = list_datasets()
    all_by_id = {dataset["id"]: dataset for dataset in all_datasets}
    children_by_parent = {}
    for dataset in all_datasets:
        parent_id = dataset.get("parent_dataset_id")
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(dataset)

    enriched = []
    for dataset in datasets:
        item = dict(dataset)
        report = get_dataset_report(item["id"]) or {}
        summary = report.get("review_summary") or {}
        pii = report.get("pii") or {}
        schema = report.get("schema") or {}
        columns = schema.get("columns") or []

        item["review_recommendation"] = summary.get("recommendation") or _fallback_review_recommendation(item)
        item["review_summary_text"] = summary.get("summary_text") or ""
        item["avg_null_rate"] = summary.get("avg_null_rate")
        item["pii_column_count"] = summary.get("pii_column_count")
        item["pii_columns"] = summary.get("pii_columns") or []
        item["high_null_column_count"] = summary.get("high_null_column_count")
        item["high_null_columns"] = summary.get("high_null_columns") or []
        item["findings"] = (summary.get("findings") or [])[:3]
        item["top_columns"] = _top_review_columns(columns)
        item["pii_counts"] = pii.get("pii_counts") or {}
        item["resubmission_parent"] = all_by_id.get(item.get("parent_dataset_id"))
        item["resubmission_children"] = sorted(
            children_by_parent.get(item["id"], []),
            key=lambda child: child["id"],
            reverse=True,
        )
        item["resubmission_count"] = len(item["resubmission_children"])
        enriched.append(item)
    return enriched


def _fallback_review_recommendation(dataset):
    if dataset.get("duplicate_status") in {"DUPLICATE", "MOSTLY_DUPLICATE"}:
        return "REJECT_RECOMMENDED"
    if float(dataset.get("pii_risk_score") or 0) >= 50:
        return "REVIEW_REQUIRED"
    if float(dataset.get("quality_score") or 0) >= 70:
        return "APPROVE_CANDIDATE"
    return "REVIEW_REQUIRED"


def _top_review_columns(columns):
    ranked = sorted(
        columns,
        key=lambda column: (
            float(column.get("null_rate") or 0),
            int(column.get("unique_count") or 0),
        ),
        reverse=True,
    )
    return ranked[:3]


def _get_purchase_filters():
    return {
        "query": request.args.get("q", "").strip(),
        "status": request.args.get("status", "").strip() or None,
    }


def _get_audit_log_filters():
    return {
        "query": request.args.get("q", "").strip(),
        "action": request.args.get("action", "").strip() or None,
        "actor_user_id": _parse_int_arg("actor_user_id"),
        "limit": _parse_int_arg("limit", default=200) or 200,
    }


def _get_access_log_filters():
    return {
        "query": request.args.get("q", "").strip(),
        "event_type": request.args.get("event_type", "").strip() or None,
        "user_id": _parse_int_arg("user_id"),
        "limit": _parse_int_arg("limit", default=200) or 200,
    }


def _admin_report_definitions(fee_rate):
    return {
        "datasets": {
            "filename": "obdm_datasets_report.csv",
            "columns": [
                "id",
                "seller_id",
                "data_name",
                "filename",
                "file_type",
                "row_count",
                "column_count",
                "quality_score",
                "pii_risk_score",
                "duplicate_status",
                "status",
                "created_at",
            ],
            "rows": list_datasets(),
        },
        "orders": {
            "filename": "obdm_orders_report.csv",
            "columns": [
                "id",
                "purchase_request_id",
                "product_id",
                "product_title",
                "buyer_id",
                "buyer_name",
                "buyer_email",
                "seller_id",
                "seller_name",
                "seller_email",
                "amount",
                "currency",
                "payment_status",
                "order_status",
                "payment_provider",
                "payment_reference",
                "paid_at",
                "created_at",
            ],
            "rows": list_orders(),
        },
        "settlements": {
            "filename": "obdm_settlements_report.csv",
            "columns": [
                "seller_id",
                "seller_name",
                "seller_email",
                "seller_company",
                "order_count",
                "gross_amount",
                "paid_amount",
                "pending_amount",
                "platform_fee",
                "settlement_due_amount",
                "settlement_status",
                "latest_paid_at",
            ],
            "rows": list_seller_settlement_summaries(fee_rate=fee_rate),
        },
        "api-usage": {
            "filename": "obdm_api_usage_report.csv",
            "columns": [
                "id",
                "api_key_id",
                "token_prefix",
                "product_id",
                "product_title",
                "user_id",
                "user_name",
                "user_email",
                "endpoint",
                "ip_address",
                "created_at",
            ],
            "rows": list_api_usage_logs(),
        },
        "downloads": {
            "filename": "obdm_downloads_report.csv",
            "columns": [
                "id",
                "product_id",
                "product_title",
                "user_id",
                "user_name",
                "user_email",
                "file_name",
                "ip_address",
                "created_at",
            ],
            "rows": list_download_logs(),
        },
    }


def _csv_response(filename, rows, columns):
    buffer = StringIO()
    buffer.write("\ufeff")
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _csv_cell(row.get(column, "")) for column in columns})

    return Response(
        buffer.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value


def _parse_float_arg(name):
    value = request.args.get(name, "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _build_operations_checklist_status():
    secret_key = os.getenv("FLASK_SECRET_KEY", "")
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_password_is_default = os.getenv("ADMIN_PASSWORD", "admin1234") == "admin1234"
    schema_status = get_schema_status()
    storage_dirs = [
        {"name": "업로드 임시 저장소", "path": UPLOAD_DIR, "exists": UPLOAD_DIR.exists()},
        {"name": "CSV 표준화 저장소", "path": CONVERTED_DIR, "exists": CONVERTED_DIR.exists()},
        {"name": "샘플 저장소", "path": SAMPLE_DIR, "exists": SAMPLE_DIR.exists()},
        {"name": "검증 리포트 저장소", "path": REPORT_DIR, "exists": REPORT_DIR.exists()},
    ]
    db_exists = DATABASE_PATH.exists()
    all_storage_ready = all(item["exists"] for item in storage_dirs)
    secret_ready = bool(secret_key and secret_key != "dev-secret-change-me")

    checks = [
        {
            "area": "보안",
            "item": "SECRET_KEY",
            "status": "PASS" if secret_ready else "ACTION",
            "message": "FLASK_SECRET_KEY가 운영용 값으로 설정되었습니다." if secret_ready else "운영 배포 전 FLASK_SECRET_KEY를 반드시 설정해야 합니다.",
        },
        {
            "area": "계정",
            "item": "관리자 부트스트랩",
            "status": "ACTION" if admin_password_is_default else "PASS",
            "message": f"관리자 이메일: {admin_email}. 기본 비밀번호 사용 여부를 점검하세요.",
        },
        {
            "area": "DB",
            "item": "SQLite",
            "status": "PASS" if db_exists and schema_status["is_current"] else "ACTION",
            "message": f"DB 파일: {DATABASE_PATH}. 마이그레이션 누락: {len(schema_status['missing_versions'])}개",
        },
        {
            "area": "파일",
            "item": "저장 디렉터리",
            "status": "PASS" if all_storage_ready else "ACTION",
            "message": "업로드, 변환, 샘플, 리포트 디렉터리 상태를 확인합니다.",
        },
        {
            "area": "보관",
            "item": "파일 보관 정책",
            "status": "PASS" if DELETE_UPLOADED_FILES_AFTER_PROCESSING and not KEEP_NORMALIZED_DATA else "REVIEW",
            "message": "원본 업로드 파일은 처리 후 삭제하고, 정규화 파일은 보관하지 않는 설정을 권장합니다.",
        },
        {
            "area": "검증",
            "item": "테스트 실행 기준",
            "status": "REVIEW",
            "message": "배포 전 TESTING.md의 회귀 테스트와 주요 화면 수동 점검을 실행합니다.",
        },
        {
            "area": "결제",
            "item": "PG 연동 준비",
            "status": "REVIEW",
            "message": "현재는 Provider/참조번호/이벤트 로그 인터페이스까지 준비되어 있으며 실제 PG 계약 연동은 후속 단계입니다.",
        },
    ]
    return {
        "checks": checks,
        "secret_ready": secret_ready,
        "admin_email": admin_email,
        "admin_password_is_default": admin_password_is_default,
        "database_path": DATABASE_PATH,
        "database_exists": db_exists,
        "schema_status": schema_status,
        "storage_dirs": storage_dirs,
        "retention": {
            "delete_uploaded_files_after_processing": DELETE_UPLOADED_FILES_AFTER_PROCESSING,
            "keep_normalized_data": KEEP_NORMALIZED_DATA,
            "keep_samples": KEEP_SAMPLES,
            "sample_size": SAMPLE_SIZE,
        },
    }


def _parse_int_arg(name, default=None):
    value = request.args.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_int_form(name, default=0):
    value = request.form.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_dataset_metadata():
    parent_dataset_id = _parse_int_form("parent_dataset_id")
    return {
        "seller_id": current_user()["id"] if current_user() else None,
        "data_name": request.form.get("data_name", ""),
        "description": request.form.get("description", ""),
        "parent_dataset_id": parent_dataset_id,
    }


def _get_resubmit_dataset_from_form():
    parent_dataset_id = _parse_int_form("parent_dataset_id")
    if not parent_dataset_id:
        return None, None

    dataset = get_dataset_summary(parent_dataset_id)
    if dataset is None:
        return None, "원본 데이터셋을 찾을 수 없습니다."
    if not _can_resubmit_dataset(dataset):
        return None, "반려된 본인 데이터만 보완 재업로드할 수 있습니다."
    return dataset, None


def _parse_int_form(name, default=None):
    value = request.form.get(name, "")
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _accepted_terms():
    value = request.form.get("accepted_terms", "")
    return str(value).strip().lower() in {"1", "true", "yes", "on", "agree", "accepted"}


def _start_upload_job(job_id, upload_path, user_pattern, metadata):
    with UPLOAD_JOBS_LOCK:
        UPLOAD_JOBS[job_id] = {
            "status": "RUNNING",
            "seller_id": metadata.get("seller_id"),
            "filename": Path(upload_path).name,
            "dataset_id": None,
            "error": None,
        }

    thread = threading.Thread(
        target=_run_upload_job,
        args=(job_id, Path(upload_path), user_pattern, metadata),
        daemon=True,
    )
    thread.start()


def _run_upload_job(job_id, upload_path, user_pattern, metadata):
    try:
        report = validate_dataset(
            upload_path,
            user_pattern=user_pattern,
            metadata=metadata,
            progress_callback=_build_progress_recorder(job_id),
        )
        attach_processing_steps_to_dataset(job_id, report["dataset_id"])
        _notify_admins(
            "DATASET_REVIEW",
            "새 데이터 검토 요청",
            f"{report['metadata']['data_name']} 데이터가 업로드되었습니다.",
            "DATASET",
            report["dataset_id"],
        )
        with UPLOAD_JOBS_LOCK:
            UPLOAD_JOBS[job_id].update({
                "status": "DONE",
                "dataset_id": report["dataset_id"],
                "error": None,
            })
    except Exception as exc:
        if upload_path.exists():
            upload_path.unlink()
        error_info = _upload_error_info(str(exc))
        _build_progress_recorder(job_id)(
            step_key="FAILED",
            step_name="처리 실패",
            status="FAILED",
            message=error_info["title"],
            detail={"reason": str(exc), "recommended_action": error_info["action"]},
            dataset_id=None,
        )
        with UPLOAD_JOBS_LOCK:
            UPLOAD_JOBS[job_id].update({
                "status": "FAILED",
                "error": str(exc),
                "error_title": error_info["title"],
                "error_action": error_info["action"],
            })


def _build_progress_recorder(job_id):
    def recorder(step_key, step_name, status, message="", detail=None, dataset_id=None):
        step = record_processing_step(
            job_id=job_id,
            dataset_id=dataset_id,
            step_key=step_key,
            step_name=step_name,
            status=status,
            message=message,
            detail=detail or {},
        )
        with UPLOAD_JOBS_LOCK:
            if job_id in UPLOAD_JOBS:
                UPLOAD_JOBS[job_id]["last_step"] = {
                    "step_key": step["step_key"],
                    "step_name": step["step_name"],
                    "status": step["status"],
                    "message": step["message"],
                }
    return recorder


def _get_upload_job(job_id):
    with UPLOAD_JOBS_LOCK:
        job = UPLOAD_JOBS.get(job_id)
        return dict(job) if job else None


def _upload_error_info(error_message):
    message = str(error_message or "").strip()
    lowered = message.lower()

    if not message:
        return {
            "title": "업로드 처리 중 오류가 발생했습니다.",
            "action": "파일을 다시 선택해 업로드해 주세요. 문제가 반복되면 관리자에게 문의해 주세요.",
        }

    if "unsupported file format" in lowered or "지원하지 않는" in message:
        return {
            "title": "지원하지 않는 파일 형식입니다.",
            "action": "CSV, JSON, JSON Lines, 구분자 텍스트, 일반 텍스트 중 하나로 변환한 뒤 다시 업로드해 주세요.",
        }

    if "parsing failed" in lowered or "tokenizing" in lowered or "expected" in lowered:
        return {
            "title": "파일 구조를 표 형식으로 읽을 수 없습니다.",
            "action": "구분자와 헤더 여부를 확인하거나, 포맷을 일반 텍스트 또는 JSON Lines로 지정해 다시 업로드해 주세요.",
        }

    if "json" in lowered:
        return {
            "title": "JSON 구조를 읽을 수 없습니다.",
            "action": "JSON 문법과 배열/객체 구조를 확인한 뒤 다시 업로드해 주세요.",
        }

    if "empty" in lowered or "no columns" in lowered:
        return {
            "title": "데이터 행 또는 컬럼을 찾을 수 없습니다.",
            "action": "파일에 헤더 또는 데이터 행이 포함되어 있는지 확인한 뒤 다시 업로드해 주세요.",
        }

    return {
        "title": "업로드 처리 중 오류가 발생했습니다.",
        "action": "파일 형식, 구분자, 인코딩을 확인한 뒤 다시 업로드해 주세요.",
    }


def _can_view_upload_job(job):
    user = current_user()
    if not user:
        return False
    if user["role"] == "ADMIN":
        return True
    return job.get("seller_id") == user["id"]


def _record_audit(action, target_type, target_id=None, detail=None):
    user = current_user()
    record_audit_log(
        actor_user_id=user["id"] if user else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail or {},
        ip_address=request.remote_addr or "",
    )


def _record_access(user_id, email, event_type, failure_reason=""):
    record_access_log(
        user_id=user_id,
        email=email or "",
        event_type=event_type,
        failure_reason=failure_reason,
        ip_address=request.remote_addr or "",
        user_agent=(request.user_agent.string or "")[:500],
    )


def _notify_user(user_id, category, title, message, target_type="", target_id=None):
    if not user_id:
        return None
    return create_notification(
        recipient_user_id=user_id,
        category=category,
        title=title,
        message=message,
        target_type=target_type,
        target_id=target_id,
    )


def _notify_admins(category, title, message, target_type="", target_id=None):
    return create_admin_notifications(
        category=category,
        title=title,
        message=message,
        target_type=target_type,
        target_id=target_id,
    )


def _get_sample_path(product):
    sample = product.get("report", {}).get("sample")
    if not sample:
        return None

    sample_path = Path(sample.get("sample_path", ""))
    if not sample_path.is_absolute():
        sample_path = Path.cwd() / sample_path
    try:
        resolved_path = sample_path.resolve()
        sample_root = SAMPLE_DIR.resolve()
        resolved_path.relative_to(sample_root)
    except (OSError, ValueError):
        return None
    return resolved_path


def _load_sample_preview(product, limit=5):
    sample_path = _get_sample_path(product)
    if sample_path is None or not sample_path.exists():
        return {"columns": [], "rows": []}

    with sample_path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        rows = []
        for index, row in enumerate(reader):
            if index >= limit:
                break
            rows.append(row)

    return {"columns": reader.fieldnames or [], "rows": rows}


def _get_current_purchase_request(product_id):
    user = current_user()
    if not user:
        return None
    return get_purchase_request_by_product_buyer(product_id, user["id"])


def get_purchase_request_by_id_for_current_user(request_id):
    user = current_user()
    if not user:
        return None
    purchase = get_purchase_request(request_id)
    if purchase is None:
        return None
    if purchase["buyer_id"] != user["id"]:
        return None
    return purchase


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _get_valid_api_key(product_id):
    token = request.headers.get("X-API-Key", "")
    if not token:
        return None

    api_key = get_api_key_by_hash(_hash_token(token))
    if api_key is None:
        return None
    if api_key["product_id"] != product_id:
        return None
    if api_key["product_status"] != "ACTIVE":
        return None
    if not _purchase_has_data_access(
        api_key["purchase_status"],
        api_key.get("product_price"),
        api_key.get("payment_status"),
    ):
        return None
    return api_key


def _can_access_product_file(product):
    user = current_user()
    if not user:
        return False
    if user["role"] == "ADMIN":
        return True
    if product.get("seller_id") == user["id"]:
        return True
    return user_has_approved_purchase(product["id"], user["id"])


def _sample_download_limit_summary(product):
    user = current_user()
    if not user:
        return None
    if user["role"] == "ADMIN" or product.get("seller_id") == user["id"]:
        return None
    return get_sample_download_summary(product["id"], user["id"])


def _can_manage_product(product):
    user = current_user()
    if not user:
        return False
    if user["role"] == "ADMIN":
        return True
    return product.get("seller_id") == user["id"]


def _can_view_purchase_request(purchase):
    user = current_user()
    if not user:
        return False
    if user["role"] == "ADMIN":
        return True
    return purchase.get("buyer_id") == user["id"] or purchase.get("seller_id") == user["id"]


def _purchase_access_summary(purchase, api_key=None, order=None):
    status = purchase.get("status")
    product_status = purchase.get("product_status")
    data_access = _purchase_has_data_access(
        status,
        purchase.get("product_price"),
        order.get("payment_status") if order else None,
    )
    active_product = product_status == "ACTIVE"
    return {
        "sample_download": data_access and active_product,
        "api_available": data_access and active_product and bool(api_key),
        "api_key_issued": bool(api_key),
        "download": get_sample_download_summary(purchase["product_id"], purchase["buyer_id"]) if data_access else None,
        "message": _purchase_access_message(status, product_status, bool(api_key), purchase.get("product_price"), order),
    }


def _purchase_has_data_access(status, product_price, payment_status=None):
    price = int(product_price or 0)
    if price <= 0 and status in {"APPROVED", "COMPLETED"}:
        return True
    return status == "COMPLETED" or payment_status == "PAID"


def _purchase_access_message(status, product_status, has_api_key, product_price=0, order=None):
    if status == "REQUESTED":
        return "관리자 승인 대기 중입니다. 승인 후 결제 또는 무료 접근 조건이 충족되면 샘플 다운로드와 API 키 발급이 가능합니다."
    if status == "REJECTED":
        return "구매 요청이 반려되었습니다. 검토 메모를 확인하세요."
    if product_status != "ACTIVE":
        return "상품이 비공개 상태라 샘플 다운로드와 API 사용이 제한됩니다."
    payment_status = order.get("payment_status") if order else None
    has_data_access = _purchase_has_data_access(status, product_price, payment_status)
    if has_data_access and has_api_key:
        return "샘플 다운로드와 API 사용이 가능합니다."
    if has_data_access:
        return "샘플 다운로드가 가능하며, 구매자 대시보드에서 API 키를 발급할 수 있습니다."
    if int(product_price or 0) > 0 and status == "APPROVED":
        return "유료 상품은 결제 완료 후 샘플 다운로드와 API 키 발급이 가능합니다."
    return "구매 요청 상태를 확인하세요."


def _can_view_dataset(report):
    user = current_user()
    if not user:
        return False
    if user["role"] == "ADMIN":
        return True
    return report.get("metadata", {}).get("seller_id") == user["id"]


def _can_edit_dataset(dataset):
    user = current_user()
    if not user or user["role"] == "ADMIN":
        return False
    if dataset.get("seller_id") != user["id"]:
        return False
    return not bool(dataset.get("product_id"))


def _can_resubmit_dataset(dataset):
    user = current_user()
    if not user or user["role"] == "ADMIN":
        return False
    if dataset.get("seller_id") != user["id"]:
        return False
    return str(dataset.get("status") or "").upper() == "REJECTED"


def _enrich_seller_dataset_progress(datasets):
    dataset_items = [dict(dataset) for dataset in datasets]
    children_by_parent = {}
    by_id = {item["id"]: item for item in dataset_items}
    for item in dataset_items:
        parent_id = item.get("parent_dataset_id")
        if parent_id:
            children_by_parent.setdefault(parent_id, []).append(item)

    enriched = []
    for dataset in dataset_items:
        item = {
            **dataset,
            "progress": _seller_dataset_progress(dataset),
        }
        item["resubmission_children"] = sorted(
            children_by_parent.get(dataset["id"], []),
            key=lambda child: child["id"],
            reverse=True,
        )
        item["resubmission_parent"] = by_id.get(dataset.get("parent_dataset_id"))
        item["resubmission_count"] = len(item["resubmission_children"])
        enriched.append(item)
    return enriched


def _seller_dataset_progress(dataset):
    status = str(dataset.get("status") or "").upper()
    product_id = dataset.get("product_id")

    if product_id:
        return {
            "label": "마켓 게시",
            "stage": 4,
            "percent": 100,
            "badge_class": "approved",
            "message": "관리자 승인이 완료되어 마켓에 게시되었습니다.",
            "next_action": "상품 정보를 확인하고 가격, 라이선스, 설명을 관리하세요.",
        }

    if status == "REJECTED":
        return {
            "label": "보완 필요",
            "stage": 3,
            "percent": 70,
            "badge_class": "rejected",
            "message": "관리자 검토에서 반려되었습니다.",
            "next_action": "검토 메모를 확인하고 데이터 이름 또는 설명을 보완한 뒤 재업로드를 준비하세요.",
        }

    if status == "APPROVED":
        return {
            "label": "승인 완료",
            "stage": 3,
            "percent": 85,
            "badge_class": "approved",
            "message": "관리자 승인이 완료되었습니다.",
            "next_action": "마켓 상품 게시 상태를 확인하세요.",
        }

    if status == "PASS":
        return {
            "label": "검토 대기",
            "stage": 2,
            "percent": 55,
            "badge_class": "review",
            "message": "자동 검증을 통과했고 관리자 검토를 기다리고 있습니다.",
            "next_action": "게시 전까지 데이터 이름과 설명을 수정할 수 있습니다.",
        }

    return {
        "label": "추가 검토",
        "stage": 2,
        "percent": 55,
        "badge_class": "review",
        "message": "자동 검증 결과 추가 검토가 필요합니다.",
        "next_action": "리포트에서 품질, 개인정보, 중복 항목을 확인하고 설명을 보완하세요.",
    }


def _dataset_resubmission_context(dataset):
    if not dataset:
        return {}

    user = current_user()
    if not user:
        return {}

    seller_id = dataset.get("seller_id")
    if user["role"] != "ADMIN" and seller_id != user["id"]:
        return {}

    seller_datasets = list_datasets_by_seller(seller_id)
    by_id = {item["id"]: item for item in seller_datasets}
    parent = by_id.get(dataset.get("parent_dataset_id"))
    children = sorted(
        [
            item
            for item in seller_datasets
            if item.get("parent_dataset_id") == dataset["id"]
        ],
        key=lambda item: item["id"],
        reverse=True,
    )

    return {
        "parent": parent,
        "children": children,
        "has_history": bool(parent or children),
    }


def bootstrap_admin():
    init_db()
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin1234")
    if get_user_by_email(admin_email):
        return

    create_user(
        name="관리자",
        email=admin_email,
        password_hash=generate_password_hash(admin_password),
        company="OBDM",
        role="ADMIN",
        status="ACTIVE",
    )


if __name__ == "__main__":
    bootstrap_admin()
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host="127.0.0.1", port=5000, debug=debug, use_reloader=False)
