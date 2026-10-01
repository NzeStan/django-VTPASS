"""
Customer notifications, wired as a signal plugin.

Off by default. When ``VTPASS["NOTIFICATIONS"]["ENABLED"]`` is True, a receiver
listens to the transaction signals and, for each event in ``EVENTS``, calls
every backend in ``BACKENDS`` (inline, or on Celery when ``USE_CELERY``):

    VTPASS = {
        "NOTIFICATIONS": {
            "ENABLED": True,
            "BACKENDS": [
                "vtpass.notifications.backends.SMSBackend",    # via VTpass Messaging
                "vtpass.notifications.backends.EmailBackend",  # via Django email
            ],
            "EVENTS": ["transaction.successful", "transaction.failed", "transaction.reversed"],
            "TEMPLATES": {
                "transaction.successful": {"sms": "{product} for {target} done. Token: {token}"},
            },
        },
    }

Write your own backend (push, WhatsApp, in-app inbox...) by subclassing
:class:`vtpass.notifications.backends.BaseNotificationBackend`.
"""

import logging
from collections import defaultdict

from vtpass.settings import vtpass_settings

logger = logging.getLogger("vtpass")

DEFAULT_TEMPLATES = {
    "transaction.successful": {
        "subject": "Your {product} purchase was successful",
        "body": (
            "Your purchase of {product} ({currency} {amount}) for {target} was successful.\n"
            "{vend_text}Reference: {reference}"
        ),
        "sms": "{product} {currency}{amount} for {target} successful. {vend_text}Ref: {reference}",
    },
    "transaction.pending": {
        "subject": "Your {product} purchase is processing",
        "body": "Your purchase of {product} ({currency} {amount}) for {target} is processing. Reference: {reference}",
        "sms": "{product} {currency}{amount} for {target} is processing. Ref: {reference}",
    },
    "transaction.failed": {
        "subject": "Your {product} purchase failed",
        "body": (
            "Your purchase of {product} ({currency} {amount}) for {target} failed.{refund_text}\n"
            "Reference: {reference}"
        ),
        "sms": "{product} {currency}{amount} for {target} failed.{refund_text} Ref: {reference}",
    },
    "transaction.reversed": {
        "subject": "Your {product} purchase was reversed",
        "body": (
            "Your purchase of {product} ({currency} {amount}) for {target} was reversed.{refund_text}\n"
            "Reference: {reference}"
        ),
        "sms": "{product} {currency}{amount} for {target} reversed.{refund_text} Ref: {reference}",
    },
}


def build_context(transaction):
    details = transaction.vend_details or {}
    token = details.get("token") or details.get("mainToken") or ""
    units = details.get("units") or details.get("Units") or details.get("mainTokenUnits") or ""
    vend_lines = []
    if token:
        vend_lines.append(f"Token: {token}" + (f" ({units} units)" if units else ""))
    elif transaction.purchased_code:
        vend_lines.append(transaction.purchased_code)
    for card in details.get("cards") or []:
        if isinstance(card, dict):
            vend_lines.append(", ".join(f"{k}: {v}" for k, v in card.items()))
    for value in details.get("tokens") or []:
        vend_lines.append(f"PIN: {value}")
    if details.get("Voucher"):
        voucher = details["Voucher"]
        vend_lines.append("Voucher: " + (", ".join(voucher) if isinstance(voucher, list) else str(voucher)))
    if details.get("certUrl"):
        vend_lines.append(f"Certificate: {details['certUrl']}")
    vend_text = ". ".join(dict.fromkeys(vend_lines))
    refund_text = ""
    if transaction.refunded:
        refund_text = f" {transaction.currency} {transaction.refund_amount} has been refunded."
    return {
        "product": transaction.product_name or transaction.service_id,
        "service_id": transaction.service_id,
        "amount": transaction.amount,
        "amount_charged": transaction.amount_charged,
        "currency": transaction.currency,
        "target": transaction.billers_code or transaction.phone,
        "phone": transaction.phone,
        "reference": transaction.request_id,
        "status": transaction.status,
        "token": token,
        "units": units,
        "cashback": transaction.cashback if transaction.cashback_paid else "",
        "vend_text": f"{vend_text}. " if vend_text else "",
        "refund_text": refund_text,
        "transaction": transaction,
    }


def render(template, context):
    return template.format_map(defaultdict(str, context)).strip()


def get_template(event, channel):
    overrides = vtpass_settings.NOTIFICATIONS.get("TEMPLATES", {}).get(event, {})
    return overrides.get(channel) or DEFAULT_TEMPLATES.get(event, {}).get(channel, "")


def get_backends():
    backends = []
    for path in vtpass_settings.NOTIFICATIONS.get("BACKENDS", []):
        backends.append(vtpass_settings.import_from_setting("NOTIFICATIONS", path)())
    return backends


def deliver(event, transaction_id):
    """Send ``event`` for a transaction through every configured backend. Failures are logged, not raised."""
    from vtpass.models import Transaction

    transaction = Transaction.objects.select_related("user").filter(pk=transaction_id).first()
    if transaction is None:
        return 0
    context = build_context(transaction)
    sent = 0
    for backend in get_backends():
        try:
            if backend.send(event, transaction, context):
                sent += 1
        except Exception:
            logger.exception("Notification backend %s failed for %s", type(backend).__name__, event)
    return sent
