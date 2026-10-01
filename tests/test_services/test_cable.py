import json
from decimal import Decimal

import pytest

from tests.conftest import BASE, pay_body
from vtpass.exceptions import VTpassValidationError

pytestmark = pytest.mark.django_db

DSTV_VARIATIONS = {
    "content": {
        "serviceID": "dstv",
        "variations": [
            {"variation_code": "dstv-padi", "name": "DStv Padi", "variation_amount": "2950.00", "fixedPrice": "Yes"},
        ],
    }
}
VERIFY = {
    "code": "000",
    "content": {
        "Customer_Name": "TEST CUSTOMER", "Status": "ACTIVE", "Current_Bouquet": "DStv Compact",
        "Renewal_Amount": 7500, "Customer_Number": "1212121212",
    },
}


def test_verify_smartcard(api, vt):
    api.post(BASE + "merchant-verify", json=VERIFY)
    assert vt.tv.verify("dstv", "1212121212")["Customer_Name"] == "TEST CUSTOMER"


def test_change_bouquet_with_quantity(api, vt, funded_user):
    api.get(BASE + "service-variations", json=DSTV_VARIATIONS)
    api.post(BASE + "pay", json=pay_body(amount=5900))
    txn = vt.tv.change("dstv", "1212121212", "dstv-padi", "08031234567", quantity=2, user=funded_user)
    assert txn.amount == Decimal("5900.00")
    sent = json.loads(api.calls[-1].request.body)
    assert sent["subscription_type"] == "change" and sent["quantity"] == 2
    assert sent["billersCode"] == "1212121212"


def test_renew_uses_renewal_amount(api, vt, funded_user):
    api.post(BASE + "merchant-verify", json=VERIFY)
    api.post(BASE + "pay", json=pay_body(amount=7500))
    txn = vt.tv.renew("dstv", "1212121212", "08031234567", user=funded_user)
    assert txn.amount == Decimal("7500.00")
    sent = json.loads(api.calls[-1].request.body)
    assert sent["subscription_type"] == "renew" and "variation_code" not in sent


def test_startimes_has_no_subscription_type(api, vt, funded_user):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "nova", "name": "Nova", "variation_amount": "1200", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json=pay_body())
    vt.tv.change("startimes", "1212121212", "nova", "08031234567", user=funded_user)
    assert "subscription_type" not in json.loads(api.calls[-1].request.body)


def test_showmax_voucher(api, vt, funded_user):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "full", "name": "Showmax", "variation_amount": "2900", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json={**pay_body(), "Voucher": ["SHMVHXQ9L3RXGPU"]})
    txn = vt.tv.showmax("08031234567", "full", user=funded_user)
    assert txn.vend_details["Voucher"] == ["SHMVHXQ9L3RXGPU"]
    assert json.loads(api.calls[-1].request.body)["billersCode"] == "08031234567"


def test_renew_only_for_dstv_gotv(vt, funded_user):
    with pytest.raises(VTpassValidationError):
        vt.tv.renew("startimes", "1212121212", "08031234567", user=funded_user)
    with pytest.raises(VTpassValidationError):
        vt.tv.verify("netflix", "1")
