import json
import re
from datetime import datetime
from decimal import Decimal

import pytest
import requests
from django.test import override_settings

from tests.conftest import BASE, pay_body
from vtpass.client import VTpassClient, VTpassResponse, resolve_status
from vtpass.constants import Status
from vtpass.exceptions import (
    VTpassAPIError,
    VTpassAuthenticationError,
    VTpassConfigError,
    VTpassMerchantError,
    VTpassNetworkError,
    VTpassValidationError,
)
from vtpass.utils import LAGOS, generate_request_id, is_valid_request_id


def test_request_id_starts_with_lagos_timestamp():
    now = datetime(2025, 3, 10, 9, 14, tzinfo=LAGOS)
    rid = generate_request_id(now=now)
    assert rid.startswith("202503100914")
    assert len(rid) == 24
    assert is_valid_request_id(rid)
    assert generate_request_id() != generate_request_id()


def test_get_uses_public_key_and_post_uses_secret_key(api):
    api.get(BASE + "service-categories", json={"response_description": "000", "content": []})
    api.post(BASE + "requery", json=pay_body())
    client = VTpassClient()
    client.get_service_categories()
    client.requery("202501011200abc")
    get_headers, post_headers = api.calls[0].request.headers, api.calls[1].request.headers
    assert get_headers["api-key"] == "test-api-key" and get_headers["public-key"] == "PK_test"
    assert "secret-key" not in get_headers
    assert post_headers["secret-key"] == "SK_test" and "public-key" not in post_headers
    assert json.loads(api.calls[1].request.body) == {"request_id": "202501011200abc"}


def test_basic_auth(api):
    api.get(BASE + "balance", json={"code": 1, "contents": {"balance": 1081.82}})
    client = VTpassClient(auth_method="basic", username="me@example.com", password="pw")
    assert client.get_balance() == Decimal("1081.82")
    assert api.calls[0].request.headers["Authorization"].startswith("Basic ")


def test_missing_credentials_raise_config_error():
    with pytest.raises(VTpassConfigError):
        VTpassClient(api_key="").get_balance()


def test_live_and_sandbox_urls():
    assert VTpassClient(sandbox=True).base_url == "https://sandbox.vtpass.com/api/"
    assert VTpassClient(sandbox=False).base_url == "https://vtpass.com/api/"
    with override_settings(VTPASS={"SANDBOX": False}):
        assert VTpassClient().base_url == "https://vtpass.com/api/"


@pytest.mark.parametrize(
    "code,status,expected",
    [
        ("000", "delivered", Status.SUCCESSFUL),
        ("000", "pending", Status.PENDING),
        ("000", "initiated", Status.PENDING),
        ("000", "failed", Status.FAILED),
        ("000", "", Status.PENDING),
        ("099", "", Status.PENDING),
        ("089", "", Status.PENDING),
        ("014", "", Status.PENDING),
        ("040", "", Status.REVERSED),
        ("000", "reversed", Status.REVERSED),
        ("016", "", Status.FAILED),
        ("018", "", Status.FAILED),
        ("091", "", Status.FAILED),
        ("", "", Status.PENDING),
    ],
)
def test_resolve_status(code, status, expected):
    assert resolve_status(code, status) == expected


def test_variations_normalises_misspelt_key(mtn_data_variations):
    content = VTpassClient().get_variations("mtn-data")
    assert [v["variation_code"] for v in content["variations"]] == ["mtn-1gb", "mtn-2gb"]
    assert "serviceID=mtn-data" in mtn_data_variations.calls[0].request.url


def test_verify_returns_customer(api):
    api.post(BASE + "merchant-verify", json={
        "code": "000", "content": {"Customer_Name": "TEST METER", "Address": "Lagos", "Meter_Number": "1111111111111"},
    })
    result = VTpassClient().verify("ikeja-electric", "1111111111111", type="prepaid")
    assert result["Customer_Name"] == "TEST METER"
    assert json.loads(api.calls[0].request.body) == {
        "billersCode": "1111111111111", "serviceID": "ikeja-electric", "type": "prepaid",
    }


def test_verify_invalid_number_raises_validation_error(api):
    api.post(BASE + "merchant-verify", json={"code": "000", "content": {"error": "Meter number is invalid"}})
    with pytest.raises(VTpassValidationError, match="invalid"):
        VTpassClient().verify("ikeja-electric", "123", type="prepaid")


def test_merchant_error_codes(api):
    api.post(BASE + "merchant-verify", json={"code": "027", "response_description": "IP NOT WHITELISTED"})
    with pytest.raises(VTpassMerchantError) as exc:
        VTpassClient().verify("dstv", "1212121212")
    assert exc.value.code == "027"


def test_invalid_credentials(api):
    api.get(BASE + "balance", status=401, json={"code": "087"})
    with pytest.raises(VTpassAuthenticationError):
        VTpassClient().get_balance()
    api.post(BASE + "pay", json={"code": "087", "response_description": "INVALID CREDENTIALS"})
    with pytest.raises(VTpassAuthenticationError):
        VTpassClient().pay(serviceID="mtn", amount=100, phone="08011111111")


def test_pay_sends_request_id_and_cleans_payload(api):
    api.post(BASE + "pay", json=pay_body())
    result = VTpassClient().pay(serviceID="mtn", amount=Decimal("100.00"), phone="08011111111", billersCode=None)
    sent = json.loads(api.calls[0].request.body)
    assert sent["amount"] == 100 and "billersCode" not in sent
    assert re.match(r"^\d{12}", sent["request_id"])
    assert result.status == Status.SUCCESSFUL
    assert result.vtpass_transaction_id == "17415980564672211596777904"


def test_pay_timeout_is_network_error_and_not_retried(api):
    api.post(BASE + "pay", body=requests.Timeout("slow"))
    with pytest.raises(VTpassNetworkError) as exc:
        VTpassClient().pay(serviceID="mtn", amount=100, phone="08011111111")
    assert exc.value.timeout is True
    assert len(api.calls) == 1


def test_non_json_5xx_is_api_error(api):
    api.post(BASE + "pay", status=502, body="<html>Bad gateway</html>")
    with pytest.raises(VTpassAPIError):
        VTpassClient().pay(serviceID="mtn", amount=100, phone="08011111111")


def test_requery_retries_network_errors(api):
    api.post(BASE + "requery", body=requests.ConnectionError("down"))
    api.post(BASE + "requery", json=pay_body())
    result = VTpassClient(backoff=0).requery("202501011200abc", retries=2)
    assert result.status == Status.SUCCESSFUL


def test_electricity_vend_details():
    response = VTpassResponse(raw={
        **pay_body(product_name="Ikeja Electric Payment - PHCN"),
        "purchased_code": "Token : 26362054405982757802",
        "mainToken": "26362054405982757802",
        "mainTokenUnits": 16.6,
        "units": "16.6 kWh",
    })
    assert response.token == "26362054405982757802"
    details = response.vend_details
    assert details["mainToken"] == "26362054405982757802"
    assert details["units"] == "16.6 kWh"


def test_commission_and_cost_fields():
    response = VTpassResponse(raw=pay_body(amount=100, total_amount=97, commission=3))
    assert response.total_amount == Decimal("97")
    assert response.commission == Decimal("3")
    assert response.commission_details["rate_type"] == "percent"


def test_international_and_insurance_lookups(api):
    api.get(BASE + "get-international-airtime-countries",
            json={"response_description": "000", "content": {"countries": [{"code": "GH", "name": "Ghana"}]}})
    api.get(BASE + "get-international-airtime-product-types",
            json={"response_description": "000", "content": [{"product_type_id": 1, "name": "Mobile Top Up"}]})
    api.get(BASE + "get-international-airtime-operators",
            json={"response_description": "000", "content": [{"operator_id": "5", "name": "MTN Ghana"}]})
    api.get(BASE + "universal-insurance/options/lga/LA",
            json={"response_description": "000", "content": [{"LGACode": "1", "LGAName": "Ikeja"}]})
    client = VTpassClient()
    assert client.get_international_countries()[0]["code"] == "GH"
    assert client.get_international_product_types("GH")[0]["product_type_id"] == 1
    assert client.get_international_operators("GH", 1)[0]["operator_id"] == "5"
    assert client.get_insurance_options("lga", "LA")[0]["LGAName"] == "Ikeja"
    assert "code=GH" in api.calls[1].request.url
    assert "product_type_id=1" in api.calls[2].request.url


def test_secrets_are_masked_in_logs(api, caplog):
    api.post(BASE + "pay", json={**pay_body(), "purchased_code": "Token : 1234567890123456"})
    with caplog.at_level("INFO", logger="vtpass"):
        VTpassClient().pay(serviceID="ikeja-electric", amount=1000, phone="08011111111")
    assert "1234567890123456" not in caplog.text
    assert "SK_test" not in caplog.text


def test_threads_get_their_own_session():
    import threading

    client = VTpassClient()
    sessions = []
    thread = threading.Thread(target=lambda: sessions.append(client.session))
    thread.start()
    thread.join()
    assert sessions[0] is not client.session
