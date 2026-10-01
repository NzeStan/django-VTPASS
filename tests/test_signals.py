"""Signal-driven plugins: notifications and Celery dispatch."""

from unittest import mock

import pytest
from django.core import mail

from tests.conftest import BASE, SMS_BASE, pay_body

pytestmark = pytest.mark.django_db

SMS_OK = {"responseCode": "TG00", "response": "MESSAGE PROCESSED", "batchId": 1, "messages": []}


@pytest.fixture
def notifications_on(settings):
    settings.VTPASS = {
        **settings.VTPASS,
        "NOTIFICATIONS": {
            "ENABLED": True,
            "ASYNC": False,
            "BACKENDS": [
                "vtpass.notifications.backends.SMSBackend",
                "vtpass.notifications.backends.EmailBackend",
            ],
        },
    }


def test_successful_purchase_notifies_by_sms_and_email(api, vt, funded_user, notifications_on,
                                                       django_capture_on_commit_callbacks):
    api.post(BASE + "pay", json={**pay_body(product_name="Ikeja Electric"), "mainToken": "1234-5678-9012"})
    api.post(SMS_BASE + "v2/api/sms/sendsms", json=SMS_OK)
    with django_capture_on_commit_callbacks(execute=True):
        vt.electricity.buy("ikedc", "1111111111111", "prepaid", 1000, "08031234567", user=funded_user)
    from urllib.parse import parse_qs

    sms_body = parse_qs(api.calls[-1].request.body)["message"][0]
    assert "Token: 1234-5678-9012" in sms_body
    assert len(mail.outbox) == 1
    assert "1234-5678-9012" in mail.outbox[0].body
    assert mail.outbox[0].to == ["ada@example.com"]


def test_failed_purchase_mentions_refund(api, vt, funded_user, notifications_on, django_capture_on_commit_callbacks):
    api.post(BASE + "pay", json={"code": "016"})
    api.post(SMS_BASE + "v2/api/sms/sendsms", json=SMS_OK)
    with django_capture_on_commit_callbacks(execute=True):
        vt.airtime.buy("08031234567", 100, user=funded_user)
    assert "refunded" in mail.outbox[0].body


def test_custom_templates(api, vt, funded_user, settings, django_capture_on_commit_callbacks):
    settings.VTPASS = {**settings.VTPASS, "NOTIFICATIONS": {
        "ENABLED": True, "ASYNC": False, "BACKENDS": ["vtpass.notifications.backends.EmailBackend"],
        "TEMPLATES": {"transaction.successful": {"subject": "Done!", "body": "Paid {amount} for {target}"}},
    }}
    api.post(BASE + "pay", json=pay_body())
    with django_capture_on_commit_callbacks(execute=True):
        vt.airtime.buy("08031234567", 100, user=funded_user)
    assert mail.outbox[0].subject == "Done!"
    assert mail.outbox[0].body == "Paid 100.00 for 08031234567"


def test_notifications_off_by_default(api, vt, funded_user, django_capture_on_commit_callbacks):
    api.post(BASE + "pay", json=pay_body())
    with django_capture_on_commit_callbacks(execute=True):
        vt.airtime.buy("08031234567", 100, user=funded_user)
    assert mail.outbox == []


def test_backend_failure_never_breaks_purchase(api, vt, funded_user, notifications_on,
                                               django_capture_on_commit_callbacks):
    api.post(BASE + "pay", json=pay_body())
    api.post(SMS_BASE + "v2/api/sms/sendsms", json={"responseCode": "TG17"})
    with django_capture_on_commit_callbacks(execute=True):
        txn = vt.airtime.buy("08031234567", 100, user=funded_user)
    assert txn.is_successful
    assert len(mail.outbox) == 1


def test_celery_dispatch(settings):
    from vtpass import jobs, tasks

    settings.VTPASS = {**settings.VTPASS, "USE_CELERY": True, "CELERY_QUEUE": "payments"}
    with mock.patch.object(tasks.requery_pending, "apply_async") as apply_async:
        jobs.dispatch("requery_pending", 10)
    apply_async.assert_called_once_with(args=(10,), kwargs={}, queue="payments")


def test_inline_dispatch_without_celery(api, vt, funded_user):
    from vtpass import jobs
    from vtpass.models import Transaction

    api.post(BASE + "pay", json={"code": "099"})
    txn = vt.airtime.buy("08031234567", 100, user=funded_user)
    api.post(BASE + "requery", json=pay_body())
    assert jobs.dispatch("requery_transaction", txn.pk) == "successful"
    assert Transaction.objects.get().is_successful


def test_celery_tasks_are_registered():
    from vtpass import tasks

    assert tasks.process_webhook.name == "vtpass.process_webhook"
    assert tasks.requery_pending.name == "vtpass.requery_pending"


def test_low_balance_signal(api, settings):
    from vtpass import jobs, signals

    settings.VTPASS = {**settings.VTPASS, "LOW_BALANCE_THRESHOLD": 5000}
    api.get(BASE + "balance", json={"code": 1, "contents": {"balance": 1200.5}})
    seen = []
    handler = lambda sender, balance, threshold, **kw: seen.append((balance, threshold))  # noqa: E731
    signals.merchant_balance_low.connect(handler)
    try:
        jobs.check_merchant_balance()
    finally:
        signals.merchant_balance_low.disconnect(handler)
    assert str(seen[0][0]) == "1200.5"
