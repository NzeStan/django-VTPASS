import json
from datetime import date
from decimal import Decimal

import pytest

from tests.conftest import BASE, pay_body
from vtpass.constants import Status
from vtpass.exceptions import VTpassValidationError

pytestmark = pytest.mark.django_db

ACCOUNT_OK = {"code": "000", "content": {"account_name": "TESTIMETRY ADAMS"}}
# Exactly the documented transfer response: no content.transactions.status.
TRANSFER_DOC_RESPONSE = {"code": "000", "response_description": "TRANSACTION SUCCESSFUL",
                         "requestId": "34w0eid28p7849i00js09440oet00", "amount": "1000.00"}


def test_bank_list(api, vt):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "gtb", "name": "GTBank", "variation_amount": "0", "fixedPrice": "No"}]}})
    assert vt.bank.banks()[0]["variation_code"] == "gtb"
    assert "serviceID=bank-deposit" in api.calls[0].request.url


def test_verify_account(api, vt):
    api.post(BASE + "merchant-verify", json=ACCOUNT_OK)
    details = vt.bank.verify_account("gtb", "1234567890")
    assert vt.bank.account_name(details) == "TESTIMETRY ADAMS"
    assert json.loads(api.calls[0].request.body) == {
        "billersCode": "1234567890", "serviceID": "bank-deposit", "type": "gtb",
    }


def test_transfer_verifies_then_settles_by_requery(api, vt, funded_user):
    from vtpass.wallets import wallet_balance

    api.post(BASE + "merchant-verify", json=ACCOUNT_OK)
    api.post(BASE + "pay", json=TRANSFER_DOC_RESPONSE)
    txn = vt.bank.transfer("gtb", "1234567890", 1000, "08031234567", user=funded_user)
    sent = json.loads(api.calls[-1].request.body)
    assert sent["serviceID"] == "bank-deposit" and sent["variation_code"] == "gtb"
    assert sent["billersCode"] == "1234567890" and sent["amount"] == 1000
    assert txn.metadata["account_name"] == "TESTIMETRY ADAMS"
    # No explicit "delivered" status: stays pending (money stays debited) until confirmed.
    assert txn.status == Status.PENDING and not txn.refunded
    assert wallet_balance(funded_user) == Decimal("9000.00")
    api.post(BASE + "requery", json=pay_body(amount=1000))
    assert vt.requery(txn).status == Status.SUCCESSFUL


def test_transfer_refused_for_unverifiable_account(api, vt, funded_user):
    api.post(BASE + "merchant-verify", json={"code": "000", "content": {"error": "Account not found"}})
    with pytest.raises(VTpassValidationError):
        vt.bank.transfer("gtb", "0000000000", 1000, "08031234567", user=funded_user)
    assert not [c for c in api.calls if c.request.url.endswith("/pay")]


def test_transfer_rejects_bad_account_number(vt, funded_user):
    with pytest.raises(VTpassValidationError):
        vt.bank.transfer("gtb", "12345", 1000, "08031234567", user=funded_user)


def test_failed_transfer_is_refunded(api, vt, funded_user):
    from vtpass.wallets import wallet_balance

    api.post(BASE + "merchant-verify", json=ACCOUNT_OK)
    api.post(BASE + "pay", json={"code": "026", "response_description": "RECIPIENT ACCOUNT COULD NOT BE VERIFIED"})
    txn = vt.bank.transfer("gtb", "1234567890", 1000, "08031234567", user=funded_user)
    assert txn.status == Status.FAILED and txn.refunded
    assert wallet_balance(funded_user) == Decimal("10000.00")


def test_personal_accident(api, vt, funded_user):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "pa-basic", "name": "Basic", "variation_amount": "1500", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json=pay_body(amount=1500))
    txn = vt.insurance.personal_accident(
        variation_code="pa-basic", phone="08031234567", full_name="Ada Obi", address="Lagos",
        dob=date(1990, 5, 1), next_kin_name="Ngozi Obi", next_kin_phone="08021234567",
        business_occupation="Trader", user=funded_user,
    )
    assert txn.amount == Decimal("1500.00") and txn.category == "insurance"
    sent = json.loads(api.calls[-1].request.body)
    assert sent["billersCode"] == "Ada Obi" and sent["dob"] == "1990-05-01"
    assert sent["serviceID"] == "personal-accident-insurance"


def test_personal_accident_requires_details(vt, funded_user):
    with pytest.raises(VTpassValidationError):
        vt.insurance.personal_accident(
            variation_code="pa-basic", phone="08031234567", full_name="Ada", address="",
            dob="1990-05-01", next_kin_name="N", next_kin_phone="0802", business_occupation="T",
            user=funded_user,
        )
