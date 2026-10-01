import json
from decimal import Decimal

import pytest

from tests.conftest import BASE, pay_body
from vtpass.exceptions import VTpassValidationError

pytestmark = pytest.mark.django_db


def test_verify_meter_with_alias(api, vt):
    api.post(BASE + "merchant-verify",
             json={"code": "000", "content": {"Customer_Name": "JOHN DOE", "Address": "Ikeja"}})
    assert vt.electricity.verify("IKEDC", "1111111111111", "prepaid")["Customer_Name"] == "JOHN DOE"
    assert json.loads(api.calls[0].request.body) == {
        "billersCode": "1111111111111", "serviceID": "ikeja-electric", "type": "prepaid",
    }


def test_prepaid_token_is_stored(api, vt, funded_user):
    api.post(BASE + "pay", json={
        **pay_body(amount=2000, product_name="Ikeja Electric Payment - PHCN"),
        "purchased_code": "Token : 26362054405982757802",
        "mainToken": "26362054405982757802",
        "units": "79.9 kWh",
        "customerName": "JOHN DOE",
    })
    txn = vt.electricity.buy("ikeja-electric", "1111111111111", "prepaid", 2000, "08031234567", user=funded_user)
    assert txn.token == "26362054405982757802"
    assert txn.vend_details["units"] == "79.9 kWh"
    assert txn.amount == Decimal("2000.00")
    sent = json.loads(api.calls[0].request.body)
    assert sent["variation_code"] == "prepaid" and sent["billersCode"] == "1111111111111"


def test_all_twelve_discos(vt):
    ids = {d["service_id"] for d in vt.electricity.discos()}
    assert len(ids) == 12 and {"aba-electric", "yola-electric", "kaduna-electric"} <= ids


def test_invalid_disco_and_meter_type(vt, funded_user):
    with pytest.raises(VTpassValidationError):
        vt.electricity.verify("nepa", "1", "prepaid")
    with pytest.raises(VTpassValidationError):
        vt.electricity.buy("ikedc", "1", "smart", 1000, "08031234567", user=funded_user)
