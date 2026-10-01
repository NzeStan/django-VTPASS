import json
from decimal import Decimal

import pytest

from tests.conftest import BASE, pay_body

pytestmark = pytest.mark.django_db

WAEC = {"content": {"variations": [
    {"variation_code": "waecdirect", "name": "WAEC Result Checker PIN", "variation_amount": "900", "fixedPrice": "Yes"},
]}}


def test_waec_result_checker_defaults_to_first_plan(api, vt, funded_user):
    api.get(BASE + "service-variations", json=WAEC)
    api.post(BASE + "pay", json={**pay_body(amount=1800), "cards": [
        {"Serial": "WRN123456790", "Pin": "098765432112"}, {"Serial": "WRN123456791", "Pin": "098765432113"},
    ]})
    txn = vt.education.waec_result_checker("08031234567", quantity=2, user=funded_user)
    assert txn.amount == Decimal("1800.00")
    assert len(txn.vend_details["cards"]) == 2
    sent = json.loads(api.calls[-1].request.body)
    assert sent["variation_code"] == "waecdirect" and sent["quantity"] == 2


def test_waec_registration_tokens(api, vt, funded_user):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "waec-registraion", "name": "WAEC Registration", "variation_amount": "3450",
         "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json={**pay_body(), "tokens": ["0100070365657400875"]})
    txn = vt.education.waec_registration("08031234567", user=funded_user)
    assert txn.vend_details["tokens"] == ["0100070365657400875"]


def test_jamb_verify_and_buy(api, vt, funded_user):
    api.post(BASE + "merchant-verify", json={"code": "000", "content": {"Customer_Name": "ADA OBI"}})
    assert vt.education.verify_jamb_profile("0123456789", "utme")["Customer_Name"] == "ADA OBI"
    assert json.loads(api.calls[0].request.body)["type"] == "utme"

    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "utme", "name": "UTME", "variation_amount": "4700", "fixedPrice": "Yes"}]}})
    pin = "Pin : 3678251321392432"
    api.post(BASE + "pay", json={**pay_body(), "Pin": pin, "purchased_code": pin})
    txn = vt.education.jamb("0123456789", "utme", "08031234567", user=funded_user)
    assert "3678251321392432" in txn.purchased_code
    assert txn.billers_code == "0123456789"
