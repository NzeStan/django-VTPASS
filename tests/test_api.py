from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from tests.conftest import BASE, SMS_BASE, pay_body
from vtpass.models import Beneficiary, Transaction

pytestmark = pytest.mark.django_db

API = "/api/vtpass/"


@pytest.fixture
def client_for():
    def make(user=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user)
        return client
    return make


@pytest.fixture
def auth(client_for, funded_user):
    return client_for(funded_user)


def test_authentication_required(client_for):
    assert client_for().post(API + "airtime/", {"phone": "08031234567", "amount": 100}).status_code == 403


def test_airtime_purchase_success(api, auth):
    api.post(BASE + "pay", json=pay_body())
    response = auth.post(API + "airtime/", {"phone": "08031234567", "amount": "100"}, format="json")
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True and body["data"]["status"] == "successful"
    assert body["data"]["service_id"] == "mtn"
    assert "cost" not in body["data"] and "vtpass_commission" not in body["data"]


def test_validation_errors(auth):
    response = auth.post(API + "airtime/", {"phone": "123", "amount": 10}, format="json")
    assert response.status_code == 400
    assert set(response.json()) >= {"phone", "amount"}


def test_idempotency_header(api, auth):
    api.post(BASE + "pay", json=pay_body())
    payload = {"phone": "08031234567", "amount": 100}
    first = auth.post(API + "airtime/", payload, format="json", HTTP_IDEMPOTENCY_KEY="abc")
    second = auth.post(API + "airtime/", payload, format="json", HTTP_IDEMPOTENCY_KEY="abc")
    assert first.json()["data"]["reference"] == second.json()["data"]["reference"]
    assert Transaction.objects.count() == 1


def test_merchant_problems_are_hidden_from_customers(api, auth):
    api.post(BASE + "pay", json={"code": "018", "response_description": "LOW WALLET BALANCE"})
    response = auth.post(API + "airtime/", {"phone": "08031234567", "amount": 100}, format="json")
    assert response.status_code == 422
    message = response.json()["message"]
    assert "LOW WALLET" not in message.upper() and "refunded" in message


def test_pending_is_202(api, auth):
    api.post(BASE + "pay", json={"code": "099"})
    response = auth.post(API + "airtime/", {"phone": "08031234567", "amount": 100}, format="json")
    assert response.status_code == 202 and response.json()["data"]["status"] == "pending"


def test_insufficient_funds_is_402(client_for, user):
    response = client_for(user).post(API + "airtime/", {"phone": "08031234567", "amount": 100}, format="json")
    assert response.status_code == 402


def test_merchant_config_error_is_503(api, auth):
    api.post(BASE + "merchant-verify", json={"code": "027", "response_description": "IP NOT WHITELISTED"})
    response = auth.post(API + "electricity/verify/",
                         {"disco": "ikedc", "meter_number": "1111111111111", "meter_type": "prepaid"}, format="json")
    assert response.status_code == 503
    assert "WHITELIST" not in response.json()["message"].upper()


def test_data_tv_electricity_education_internet(api, auth):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "p1", "name": "Plan", "variation_amount": "500", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json=pay_body())
    api.post(BASE + "merchant-verify", json={"code": "000", "content": {"Customer_Name": "X", "Renewal_Amount": 500}})
    calls = [
        ("data/", {"phone": "08031234567", "variation_code": "p1"}),
        ("tv/", {"provider": "gotv", "smartcard_number": "1212121212", "phone": "08031234567", "variation_code": "p1"}),
        ("tv/", {"provider": "dstv", "action": "renew", "smartcard_number": "1212121212", "phone": "08031234567"}),
        ("tv/", {"provider": "showmax", "phone": "08031234567", "variation_code": "p1"}),
        ("electricity/", {"disco": "eko", "meter_number": "1111111111111", "meter_type": "postpaid",
                          "amount": 1000, "phone": "08031234567"}),
        ("education/", {"product": "waec", "phone": "08031234567", "quantity": 1}),
        ("education/", {"product": "jamb", "phone": "08031234567", "profile_id": "0123456789", "variation_code": "p1"}),
        ("internet/", {"provider": "spectranet", "phone": "08031234567", "variation_code": "p1"}),
        ("internet/", {"provider": "smile-direct", "phone": "08031234567", "variation_code": "p1",
                       "account_id": "2348011111111"}),
        ("purchase/", {"service_id": "glo", "phone": "08051234567", "amount": 100}),
    ]
    for path, payload in calls:
        response = auth.post(API + path, payload, format="json")
        assert response.status_code == 201, (path, response.json())
    for path in ("tv/verify/", "electricity/verify/", "education/jamb/verify/", "verify/"):
        payload = {"provider": "dstv", "smartcard_number": "1", "disco": "ikedc", "meter_number": "1",
                   "meter_type": "prepaid", "profile_id": "1", "variation_code": "utme", "service_id": "dstv",
                   "billers_code": "1"}
        assert auth.post(API + path, payload, format="json").status_code == 200, path


def test_insurance_and_international(api, auth):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "1", "name": "Private", "variation_amount": "3000", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json=pay_body())
    api.get(BASE + "universal-insurance/options/state", json={"content": [{"StateCode": "LA"}]})
    assert auth.get(API + "insurance/options/state/").json()["data"] == [{"StateCode": "LA"}]
    assert auth.get(API + "insurance/options/bogus/").status_code == 404
    response = auth.post(API + "insurance/", {
        "plate_number": "AAA123BB", "variation_code": "1", "phone": "08031234567", "email": "a@b.com",
        "insured_name": "Ada", "engine_capacity": "1", "chasis_number": "C1", "vehicle_make": "TOY",
        "vehicle_color": "RED", "vehicle_model": "COR", "year_of_make": "2015", "state": "LA", "lga": "IKJ",
    }, format="json")
    assert response.status_code == 201
    api.get(BASE + "get-international-airtime-countries", json={"content": {"countries": [{"code": "GH"}]}})
    assert auth.get(API + "international/countries/").json()["data"] == [{"code": "GH"}]
    assert auth.get(API + "international/operators/?country=GH").status_code == 400
    response = auth.post(API + "international/", {
        "recipient": "233241234567", "country_code": "GH", "operator_id": "5", "product_type_id": "1",
        "variation_code": "1", "phone": "08031234567", "email": "a@b.com",
    }, format="json")
    assert response.status_code == 201


def test_transactions_are_private(api, client_for, funded_user, other_user, staff):
    api.post(BASE + "pay", json=pay_body())
    owner = client_for(funded_user)
    reference = owner.post(API + "airtime/", {"phone": "08031234567", "amount": 100}, format="json").json()["data"][
        "reference"]
    assert owner.get(API + "transactions/").json()["data"]["results"][0]["reference"] == reference
    assert owner.get(API + f"transactions/{reference}/").status_code == 200
    assert client_for(other_user).get(API + "transactions/").json()["data"]["count"] == 0
    assert client_for(other_user).get(API + f"transactions/{reference}/").status_code == 404
    assert client_for(staff).get(API + f"transactions/{reference}/").status_code == 200


def test_requery_endpoint(api, auth):
    api.post(BASE + "pay", json={"code": "099"})
    reference = auth.post(API + "airtime/", {"phone": "08031234567", "amount": 100}, format="json").json()["data"][
        "reference"]
    api.post(BASE + "requery", json=pay_body())
    response = auth.post(API + f"transactions/{reference}/requery/")
    assert response.json()["data"]["status"] == "successful"


def test_wallet_and_entries(api, auth):
    assert auth.get(API + "wallet/").json()["data"]["balance"] == "10000.00"
    api.post(BASE + "pay", json=pay_body())
    auth.post(API + "airtime/", {"phone": "08031234567", "amount": 100}, format="json")
    entries = auth.get(API + "wallet/entries/").json()["data"]["results"]
    assert [e["kind"] for e in entries] == ["purchase", "funding"]


def test_beneficiaries_crud(auth, client_for, other_user):
    payload = {"service_id": "ikeja-electric", "billers_code": "1111111111111", "nickname": "Home"}
    created = auth.post(API + "beneficiaries/", payload, format="json")
    assert created.status_code == 201
    assert auth.post(API + "beneficiaries/", payload, format="json").status_code == 409
    uid = created.json()["data"]["id"]
    assert auth.patch(API + f"beneficiaries/{uid}/", {"nickname": "Mum"}, format="json").json()["nickname"] == "Mum"
    assert client_for(other_user).get(API + f"beneficiaries/{uid}/").status_code == 404
    assert auth.delete(API + f"beneficiaries/{uid}/").status_code == 204
    assert not Beneficiary.objects.exists()


def test_catalog_quote_and_network(api, auth):
    api.get(BASE + "service-categories", json={"content": [{"identifier": "airtime", "name": "Airtime"}]})
    assert auth.get(API + "catalog/categories/").json()["data"][0]["identifier"] == "airtime"
    assert auth.get(API + "catalog/services/").status_code == 400
    assert auth.get(API + "networks/detect/?phone=08051234567").json()["data"]["network"] == "glo"
    quote = auth.post(API + "quote/", {"service_id": "mtn", "amount": 500}, format="json").json()["data"]
    assert Decimal(quote["amount_payable"]) == Decimal("500")


def test_admin_endpoints(api, client_for, funded_user, staff):
    assert client_for(funded_user).get(API + "merchant/balance/").status_code == 403
    assert client_for(funded_user).post(API + "sms/send/", {}).status_code == 403
    api.get(BASE + "balance", json={"code": 1, "contents": {"balance": 5000}})
    assert client_for(staff).get(API + "merchant/balance/").json()["data"]["balance"] == "5000"
    api.post(SMS_BASE + "v2/api/sms/sendsms", json={"responseCode": "TG00", "batchId": 9, "messages": []})
    payload = {"recipients": ["08031234567"], "message": "Hi"}
    response = client_for(staff).post(API + "sms/send/", payload, format="json")
    assert response.status_code == 200 and response.json()["data"]["batch_id"] == "9"


def test_earnings_report(api, client_for, funded_user, staff):
    api.post(BASE + "pay", json=pay_body(amount=1000, total_amount=970, commission=30))
    client_for(funded_user).post(API + "airtime/", {"phone": "08031234567", "amount": 1000}, format="json")
    report = client_for(staff).get(API + "reports/earnings/").json()["data"]
    assert report["overall"]["count"] == 1
    assert report["overall"]["profit"] == "30.00"
    assert report["by_category"][0]["category"] == "airtime"


def test_generic_purchase_can_be_disabled(auth, settings):
    settings.VTPASS = {**settings.VTPASS, "API": {**settings.VTPASS["API"], "ALLOW_GENERIC_PURCHASE": False}}
    response = auth.post(API + "purchase/", {"service_id": "mtn", "phone": "08031234567", "amount": 100}, format="json")
    assert response.status_code == 404


def test_purchase_throttling(api, auth, settings):
    settings.VTPASS = {**settings.VTPASS, "API": {**settings.VTPASS["API"], "PURCHASE_THROTTLE_RATE": "2/min"}}
    api.post(BASE + "pay", json=pay_body())
    statuses = [
        auth.post(API + "airtime/", {"phone": "08031234567", "amount": 100}, format="json").status_code
        for _ in range(3)
    ]
    assert statuses == [201, 201, 429]


def test_tv_renew_ignores_client_amount(api, auth):
    import json

    api.post(BASE + "merchant-verify", json={"code": "000", "content": {"Renewal_Amount": 4500}})
    api.post(BASE + "pay", json=pay_body())
    response = auth.post(API + "tv/", {"provider": "dstv", "action": "renew", "smartcard_number": "1212121212",
                                       "phone": "08031234567", "amount": 1}, format="json")
    assert response.json()["data"]["amount_charged"] == "4500.00"
    assert json.loads(api.calls[-1].request.body)["amount"] == 4500


def test_generic_purchase_rejects_protected_extra(auth):
    response = auth.post(API + "purchase/", {"service_id": "mtn-data", "phone": "08031234567", "amount": 100,
                                             "extra": {"variation_code": "mtn-100gb"}}, format="json")
    assert response.status_code == 400


def test_lists_are_paginated(api, auth):
    api.post(BASE + "pay", json=pay_body())
    for _ in range(3):
        auth.post(API + "airtime/", {"phone": "08031234567", "amount": 100}, format="json")
    page = auth.get(API + "transactions/?page_size=2").json()["data"]
    assert page["count"] == 3 and len(page["results"]) == 2 and page["next"]


def test_bank_transfer_endpoints(api, auth):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "gtb", "name": "GTBank", "variation_amount": "0", "fixedPrice": "No"}]}})
    api.post(BASE + "merchant-verify", json={"code": "000", "content": {"account_name": "TESTIMETRY ADAMS"}})
    api.post(BASE + "pay", json=pay_body())
    assert auth.get(API + "bank-transfer/banks/").json()["data"][0]["variation_code"] == "gtb"
    verified = auth.post(API + "bank-transfer/verify/", {"bank_code": "gtb", "account_number": "1234567890"},
                         format="json").json()
    assert verified["data"]["account_name"] == "TESTIMETRY ADAMS"
    assert auth.post(API + "bank-transfer/", {"bank_code": "gtb", "account_number": "123",
                                              "amount": 500, "phone": "08031234567"}, format="json").status_code == 400
    response = auth.post(API + "bank-transfer/", {"bank_code": "gtb", "account_number": "1234567890",
                                                  "amount": 500, "phone": "08031234567"}, format="json")
    assert response.status_code == 201


def test_personal_accident_endpoint(api, auth):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "pa", "name": "Basic", "variation_amount": "1500", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json=pay_body())
    assert auth.get(API + "insurance/plans/?product=personal-accident-insurance").status_code == 200
    assert auth.get(API + "insurance/plans/?product=nope").status_code == 404
    response = auth.post(API + "insurance/personal-accident/", {
        "variation_code": "pa", "phone": "08031234567", "full_name": "Ada Obi", "address": "Lagos",
        "dob": "1990-05-01", "next_kin_name": "Ngozi", "next_kin_phone": "08021234567",
        "business_occupation": "Trader",
    }, format="json")
    assert response.status_code == 201
