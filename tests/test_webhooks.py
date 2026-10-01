import json
from decimal import Decimal

import pytest

from tests.conftest import BASE, pay_body
from vtpass.constants import Status
from vtpass.models import Service, Transaction, WebhookEvent

pytestmark = pytest.mark.django_db

URL = "/vtpass/webhook/hook-secret/"


def post(client, payload, url=URL, **extra):
    return client.post(url, data=json.dumps(payload), content_type="application/json", **extra)


def update_payload(request_id, code="000", status="delivered"):
    return {"type": "transaction-update", "data": {
        "code": code, "requestId": request_id, "response_description": "TRANSACTION DELIVERED",
        "content": {"transactions": {"status": status, "transactionId": "1583519914158857111079"}},
    }}


@pytest.fixture
def pending_txn(api, vt, funded_user):
    api.post(BASE + "pay", json={"code": "099"})
    return vt.airtime.buy("08031234567", 100, user=funded_user)


def test_acknowledges_with_expected_body(client, pending_txn, api, django_capture_on_commit_callbacks):
    api.post(BASE + "requery", json=pay_body())
    with django_capture_on_commit_callbacks(execute=True):
        response = post(client, update_payload(pending_txn.request_id))
    assert response.status_code == 200 and response.json() == {"response": "success"}
    pending_txn.refresh_from_db()
    assert pending_txn.status == Status.SUCCESSFUL
    assert WebhookEvent.objects.get().state == WebhookEvent.PROCESSED


def test_payload_is_not_trusted_without_requery(client, pending_txn, api, django_capture_on_commit_callbacks):
    """A forged 'delivered' callback cannot settle a transaction VTpass says is still processing."""
    api.post(BASE + "requery", json={"code": "099"})
    with django_capture_on_commit_callbacks(execute=True):
        post(client, update_payload(pending_txn.request_id))
    pending_txn.refresh_from_db()
    assert pending_txn.status == Status.PENDING


def test_reversal_callback_refunds(client, api, vt, funded_user, django_capture_on_commit_callbacks):
    from vtpass.wallets import wallet_balance

    api.post(BASE + "pay", json=pay_body(amount=100))
    txn = vt.airtime.buy("08031234567", 100, user=funded_user)
    api.post(BASE + "requery", json={"code": "040", "content": {"transactions": {"status": "reversed"}}})
    with django_capture_on_commit_callbacks(execute=True):
        post(client, update_payload(txn.request_id, code="040", status="reversed"))
    txn.refresh_from_db()
    assert txn.status == Status.REVERSED and txn.refunded
    assert wallet_balance(funded_user) == Decimal("10000.00")


def test_payload_trusted_when_configured(client, pending_txn, settings, django_capture_on_commit_callbacks):
    settings.VTPASS = {**settings.VTPASS, "WEBHOOK": {"TOKEN": "hook-secret", "VERIFY_WITH_REQUERY": False}}
    with django_capture_on_commit_callbacks(execute=True):
        post(client, update_payload(pending_txn.request_id))
    pending_txn.refresh_from_db()
    assert pending_txn.status == Status.SUCCESSFUL


def test_wrong_or_missing_token_is_404(client):
    assert post(client, update_payload("x"), url="/vtpass/webhook/wrong/").status_code == 404
    assert post(client, update_payload("x"), url="/vtpass/webhook/").status_code == 404


def test_ip_allowlist(client, settings):
    settings.VTPASS = {**settings.VTPASS, "WEBHOOK": {"TOKEN": "hook-secret", "ALLOWED_IPS": ["10.0.0.1"]}}
    assert post(client, update_payload("x"), REMOTE_ADDR="1.2.3.4").status_code == 403
    assert post(client, update_payload("x"), REMOTE_ADDR="10.0.0.1").status_code == 200


def test_bad_requests(client):
    assert client.get(URL).status_code == 405
    assert client.post(URL, data="not json", content_type="application/json").status_code == 400
    assert post(client, ["list"]).status_code == 400
    assert post(client, {"no": "type"}).status_code == 400


def test_unknown_transaction_is_ignored(client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        assert post(client, update_payload("202501010000unknown")).status_code == 200
    assert WebhookEvent.objects.get().state == WebhookEvent.IGNORED


def test_retries_are_deduplicated(client, pending_txn, api, django_capture_on_commit_callbacks):
    api.post(BASE + "requery", json=pay_body())
    with django_capture_on_commit_callbacks(execute=True):
        post(client, update_payload(pending_txn.request_id))
        post(client, update_payload(pending_txn.request_id))
    event = WebhookEvent.objects.get()
    assert event.attempts == 2
    assert Transaction.objects.get().status == Status.SUCCESSFUL


def test_variations_update_resyncs_service(client, api, django_capture_on_commit_callbacks):
    from vtpass import signals

    api.get(BASE + "service-variations", json={"response_description": "000", "content": {
        "ServiceName": "Smile Payment", "serviceID": "smile-direct", "convinience_fee": "N0.00",
        "variations": [{"variation_code": "624", "name": "2GB", "variation_amount": "1020.00", "fixedPrice": "Yes"}],
    }})
    seen = []
    handler = lambda sender, service_id, **kw: seen.append(service_id)  # noqa: E731
    signals.variations_updated.connect(handler)
    try:
        with django_capture_on_commit_callbacks(execute=True):
            post(client, {"type": "variations-update", "serviceID": "smile-direct", "summary": {}, "data": {}})
    finally:
        signals.variations_updated.disconnect(handler)
    service = Service.objects.get(service_id="smile-direct")
    assert service.variations.get().variation_code == "624"
    assert service.category.identifier == "data"
    assert seen == ["smile-direct"]
