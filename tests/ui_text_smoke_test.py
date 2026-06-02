from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, bootstrap_admin
from data_marketplace.database import get_user_by_email


def page_text(client, path: str) -> str:
    response = client.get(path)
    if response.status_code != 200:
        raise AssertionError(f"{path} returned {response.status_code}")
    return response.data.decode("utf-8")


def assert_contains(text: str, *phrases: str) -> None:
    missing = [phrase for phrase in phrases if phrase not in text]
    if missing:
        raise AssertionError(f"missing UI phrases: {missing}")


def assert_not_contains(text: str, *phrases: str) -> None:
    found = [phrase for phrase in phrases if phrase in text]
    if found:
        raise AssertionError(f"unexpected UI phrases: {found}")


def main() -> None:
    bootstrap_admin()
    admin = get_user_by_email("admin@example.com")
    if admin is None:
        raise AssertionError("default admin account is missing")

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = admin["id"]
        session["csrf_token"] = "ui-text-token"

    login_text = page_text(client, "/login")
    assert_contains(login_text, "OBDM", "Onbranding Data Market", "로그인", "이메일", "비밀번호")
    assert_not_contains(login_text, "All Data", "Daya", "brand-mark", ">OB<")

    market_text = page_text(client, "/market")
    assert_contains(market_text, "데이터 마켓", "검색어", "카테고리", "품질", "정렬")
    assert_not_contains(market_text, "All Data", "Daya", "brand-mark", ">OB<")

    dashboard_text = page_text(client, "/user/dashboard")
    assert_contains(dashboard_text, "내 대시보드", "내가 올린 데이터", "판매 예상 매출", "주문/결제 내역")
    assert_not_contains(dashboard_text, "All Data", "Daya", "brand-mark", ">OB<")

    buyer_orders_text = page_text(client, "/web/orders")
    assert_contains(buyer_orders_text, "내 주문/결제 내역", "주문 목록")
    assert_not_contains(buyer_orders_text, "All Data", "Daya", "brand-mark", ">OB<")

    admin_text = page_text(client, "/web/admin")
    assert_contains(admin_text, "관리자 운영 대시보드", "오늘의 운영 현황", "검토 리스크 요약", "주문 준비 목록", "주문 CSV")
    assert_not_contains(admin_text, "All Data", "Daya", "brand-mark", ">OB<")

    settlement_text = page_text(client, "/web/admin/settlements")
    assert_contains(settlement_text, "관리자 정산 화면", "플랫폼 수수료", "정산 예정액", "정산 CSV 내보내기")
    assert_not_contains(settlement_text, "All Data", "Daya", "brand-mark", ">OB<")

    admin_products_text = page_text(client, "/web/admin/products")
    assert_contains(admin_products_text, "마켓 상품", "검색", "상태", "정렬")
    assert_not_contains(admin_products_text, "All Data", "Daya", "brand-mark", ">OB<")

    admin_datasets_text = page_text(client, "/web/admin/datasets")
    assert_contains(admin_datasets_text, "관리자 검토", "검토 목록", "판단", "승인 후보")
    assert_not_contains(admin_datasets_text, "All Data", "Daya", "brand-mark", ">OB<")

    operations_text = page_text(client, "/web/admin/operations-checklist")
    assert_contains(operations_text, "운영 점검표", "파일 보관 정책", "테스트 실행 기준", "PG 연동 준비", "DB 백업")
    assert_not_contains(operations_text, "All Data", "Daya", "brand-mark", ">OB<")

    seller_purchases_text = page_text(client, "/web/seller/purchases")
    assert_contains(seller_purchases_text, "내 상품 구매 요청", "요청 목록")
    assert_not_contains(seller_purchases_text, "All Data", "Daya", "brand-mark", ">OB<")

    seller_reports_text = page_text(client, "/web/seller/reports")
    assert_contains(seller_reports_text, "판매자 상품 운영 리포트", "상품별 운영 현황", "API 호출")
    assert_not_contains(seller_reports_text, "All Data", "Daya", "brand-mark", ">OB<")

    print("UI_TEXT_SMOKE_TEST_PASS")


if __name__ == "__main__":
    main()
