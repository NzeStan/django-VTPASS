from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse

from tests.conftest import BASE, SMS_BASE, pay_body
from vtpass.models import Transaction

pytestmark = pytest.mark.django_db

MODELS = [
    "transaction", "pricingrule", "servicecategory", "service", "variation", "wallet", "walletentry",
    "beneficiary", "webhookevent", "smsmessage",
]


@pytest.mark.parametrize("model", MODELS)
def test_admin_changelists_load(admin_client, model):
    assert admin_client.get(reverse(f"admin:vtpass_{model}_changelist")).status_code == 200


def test_ledgers_are_read_only(admin_client):
    assert admin_client.get(reverse("admin:vtpass_transaction_add")).status_code == 403
    assert admin_client.get(reverse("admin:vtpass_walletentry_add")).status_code == 403


def test_transaction_detail_and_requery_action(api, admin_client, vt, funded_user):
    api.post(BASE + "pay", json={"code": "099"})
    txn = vt.airtime.buy("08031234567", 100, user=funded_user)
    assert admin_client.get(reverse("admin:vtpass_transaction_change", args=[txn.pk])).status_code == 200
    api.post(BASE + "requery", json=pay_body())
    admin_client.post(reverse("admin:vtpass_transaction_changelist"),
                      {"action": "requery_selected", "_selected_action": [txn.pk]})
    assert Transaction.objects.get().is_successful


def test_commands(api, vt, funded_user):
    out = StringIO()
    api.get(BASE + "balance", json={"code": 1, "contents": {"balance": 1500}})
    api.get(SMS_BASE + "api/sms/balance", body="20")
    call_command("vtpass_balance", "--sms", stdout=out)
    assert "1500" in out.getvalue() and "20" in out.getvalue()

    api.post(BASE + "pay", json={"code": "099"})
    txn = vt.airtime.buy("08031234567", 100, user=funded_user)
    api.post(BASE + "requery", json=pay_body())
    call_command("vtpass_requery_pending", "--reference", txn.request_id, stdout=out)
    assert "successful" in out.getvalue()
    call_command("vtpass_requery_pending", stdout=out)

    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "a", "name": "A", "variation_amount": "1", "fixedPrice": "Yes"}]}})
    call_command("vtpass_sync_catalog", "--service", "mtn-data", stdout=out)
    assert "mtn-data: 1 plan(s)" in out.getvalue()

    api.post(SMS_BASE + "v2/api/sms/sendsms", json={"responseCode": "TG00", "response": "OK", "batchId": 3})
    call_command("vtpass_send_sms", "08031234567", "Hello", stdout=out)
    assert "TG00" in out.getvalue()


def test_system_checks(settings):
    from vtpass.apps import check_configuration

    assert check_configuration() == []
    settings.VTPASS = {"SANDBOX": False}
    ids = {m.id for m in check_configuration()}
    assert {"vtpass.W001", "vtpass.W002"} <= ids
