from __future__ import annotations

from typing import Any

from data_marketplace.database import update_order_payment_status


PAYMENT_PROVIDER_MANUAL = "MANUAL"
PAYMENT_STATUS_REQUESTED = "PAYMENT_REQUESTED"
PAYMENT_STATUS_PAID = "PAID"
PAYMENT_STATUS_FAILED = "FAILED"
PAYMENT_STATUS_CANCELED = "CANCELED"


def request_payment(
    order_id: int,
    note: str = "",
    provider: str = PAYMENT_PROVIDER_MANUAL,
    provider_reference: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return _transition_payment(
        order_id,
        PAYMENT_STATUS_REQUESTED,
        note,
        provider,
        provider_reference,
        "PAYMENT_REQUESTED",
        detail,
    )


def confirm_payment(
    order_id: int,
    note: str = "",
    provider: str = PAYMENT_PROVIDER_MANUAL,
    provider_reference: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return _transition_payment(
        order_id,
        PAYMENT_STATUS_PAID,
        note,
        provider,
        provider_reference,
        "PAYMENT_CONFIRMED",
        detail,
    )


def fail_payment(
    order_id: int,
    note: str = "",
    provider: str = PAYMENT_PROVIDER_MANUAL,
    provider_reference: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return _transition_payment(
        order_id,
        PAYMENT_STATUS_FAILED,
        note,
        provider,
        provider_reference,
        "PAYMENT_FAILED",
        detail,
    )


def cancel_payment(
    order_id: int,
    note: str = "",
    provider: str = PAYMENT_PROVIDER_MANUAL,
    provider_reference: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return _transition_payment(
        order_id,
        PAYMENT_STATUS_CANCELED,
        note,
        provider,
        provider_reference,
        "PAYMENT_CANCELED",
        detail,
    )


def transition_payment_status(
    order_id: int,
    payment_status: str,
    note: str = "",
    provider: str = PAYMENT_PROVIDER_MANUAL,
    provider_reference: str = "",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    normalized = str(payment_status or "").strip().upper()
    if normalized == PAYMENT_STATUS_REQUESTED:
        return request_payment(order_id, note, provider, provider_reference, detail)
    if normalized == PAYMENT_STATUS_PAID:
        return confirm_payment(order_id, note, provider, provider_reference, detail)
    if normalized == PAYMENT_STATUS_FAILED:
        return fail_payment(order_id, note, provider, provider_reference, detail)
    if normalized == PAYMENT_STATUS_CANCELED:
        return cancel_payment(order_id, note, provider, provider_reference, detail)

    return _transition_payment(
        order_id,
        normalized,
        note,
        provider,
        provider_reference,
        "PAYMENT_STATUS_UPDATED",
        detail,
    )


def _transition_payment(
    order_id: int,
    payment_status: str,
    note: str,
    provider: str,
    provider_reference: str,
    event_type: str,
    detail: dict[str, Any] | None,
) -> dict[str, Any] | None:
    return update_order_payment_status(
        order_id=order_id,
        payment_status=payment_status,
        payment_note=note,
        payment_provider=provider,
        payment_reference=provider_reference,
        event_type=event_type,
        detail=detail,
    )
