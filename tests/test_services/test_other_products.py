"""Internet (Smile, Spectranet), insurance and international airtime."""

import json
from decimal import Decimal

import pytest

from tests.conftest import BASE, pay_body
from vtpass.exceptions import VTpassValidationError

pytestmark = pytest.mark.django_db


def test_smile_email_lookup_and_purchase(api, vt, funded_user):
    api.post(BASE + "merchant-verify/smile/email", json={"code": "000", "content": {
        "Customer_Name": "Tester", "AccountList": {"Account": [{"AccountId": 2348011111111}]}}})
    assert vt.internet.verify_smile_email("tester@sandbox.com")["Customer_Name"] == "Tester"

    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "516", "name": "1GB", "variation_amount": "510.00", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json=pay_body())
    txn = vt.internet.buy_smile("08011111111", "516", "08031234567", user=funded_user)
    assert txn.service_id == "smile-direct" and txn.amount == Decimal("510.00")


def test_spectranet_cards(api, vt, funded_user):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "s1000", "name": "N1000", "variation_amount": "1000", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json={**pay_body(), "cards": [{"serialNumber": "123", "pin": "456", "expiresOn": "2026"}]})
    txn = vt.internet.buy_spectranet("08031234567", "s1000", quantity=2, user=funded_user)
    assert txn.amount == Decimal("2000.00")
    assert txn.vend_details["cards"][0]["pin"] == "456"


INSURANCE_DETAILS = dict(
    plate_number="AAA123BB", variation_code="1", phone="08031234567", insured_name="Ada Obi",
    engine_capacity="1", chasis_number="CH123", vehicle_make="TOY", vehicle_color="RED", vehicle_model="COR",
    year_of_make="2015", state="LA", lga="IKJ", email="ada@example.com",
)


def test_third_party_motor_insurance(api, vt, funded_user):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "1", "name": "Private", "variation_amount": "3000", "fixedPrice": "Yes"}]}})
    api.post(BASE + "pay", json={**pay_body(), "certUrl": "https://vtpass.com/cert/123.pdf"})
    txn = vt.insurance.third_party_motor(**INSURANCE_DETAILS, user=funded_user)
    assert txn.vend_details["certUrl"].endswith(".pdf")
    sent = json.loads(api.calls[-1].request.body)
    assert sent["Insured_Name"] == "Ada Obi" and sent["YearofMake"] == "2015" and sent["billersCode"] == "AAA123BB"


def test_insurance_requires_all_details(vt, funded_user):
    with pytest.raises(VTpassValidationError):
        vt.insurance.third_party_motor(**{**INSURANCE_DETAILS, "insured_name": ""}, user=funded_user)


def test_insurance_options_are_cached_and_validated(api, vt):
    api.get(BASE + "universal-insurance/options/brand", json={"content": [{"VehicleMakeCode": "TOY"}]})
    vt.insurance.options("brand")
    vt.insurance.options("brand")
    assert len(api.calls) == 1
    with pytest.raises(VTpassValidationError):
        vt.insurance.options("model")
    with pytest.raises(VTpassValidationError):
        vt.insurance.options("colour")


def test_international_airtime(api, vt, funded_user):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "flex", "name": "Top up", "variation_amount": "0", "fixedPrice": "No"}]}})
    api.post(BASE + "pay", json=pay_body())
    txn = vt.international.buy(
        recipient="+233 24 123 4567", country_code="gh", operator_id="5", product_type_id="1",
        variation_code="flex", email="ada@example.com", phone="08031234567", amount=1500, user=funded_user,
    )
    assert txn.amount == Decimal("1500.00") and txn.billers_code == "233241234567"
    sent = json.loads(api.calls[-1].request.body)
    assert sent["country_code"] == "GH" and sent["operator_id"] == "5" and sent["product_type_id"] == "1"
    assert "operator_id=5" in api.calls[0].request.url


def test_international_flexible_plan_needs_amount(api, vt, funded_user):
    api.get(BASE + "service-variations", json={"content": {"variations": [
        {"variation_code": "flex", "name": "Top up", "variation_amount": "0", "fixedPrice": "No"}]}})
    with pytest.raises(VTpassValidationError):
        vt.international.buy(
            recipient="233241234567", country_code="GH", operator_id="5", product_type_id="1",
            variation_code="flex", email="ada@example.com", phone="08031234567", user=funded_user,
        )


def test_quote(api, vt):
    from vtpass.models import PricingRule

    PricingRule.objects.create(name="fee", service_id="ikeja-electric", fee_type="flat", fee_value=100)
    quote = vt.quote("ikeja-electric", amount=5000)
    assert quote.amount_payable == Decimal("5100.00")
