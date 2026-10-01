import json
from decimal import Decimal

import pytest

from tests.conftest import BASE, pay_body
from vtpass.exceptions import VTpassValidationError
from vtpass.models import Service, ServiceCategory, Variation

pytestmark = pytest.mark.django_db


def test_plans_are_fetched_and_cached(mtn_data_variations, vt):
    assert [p["variation_code"] for p in vt.data.plans("mtn")] == ["mtn-1gb", "mtn-2gb"]
    vt.data.plans("mtn")
    assert len(mtn_data_variations.calls) == 1


def test_buy_uses_plan_price(mtn_data_variations, vt, funded_user):
    mtn_data_variations.post(BASE + "pay", json=pay_body(amount=600))
    txn = vt.data.buy("08031234567", "mtn-2gb", user=funded_user)
    assert txn.amount == Decimal("600.00") and txn.product_name == "MTN 2GB"
    sent = json.loads(mtn_data_variations.calls[-1].request.body)
    assert sent["billersCode"] == "08031234567" and sent["variation_code"] == "mtn-2gb"
    assert sent["serviceID"] == "mtn-data"


def test_client_supplied_amount_cannot_undercut_fixed_price(mtn_data_variations, vt, funded_user):
    mtn_data_variations.post(BASE + "pay", json=pay_body())
    txn = vt.data.buy("08031234567", "mtn-2gb", amount=1, user=funded_user)
    assert txn.amount == Decimal("600.00")


def test_unknown_plan(mtn_data_variations, vt, funded_user):
    with pytest.raises(VTpassValidationError):
        vt.data.buy("08031234567", "mtn-999tb", user=funded_user)


def test_glo_sme(api, vt):
    api.get(BASE + "service-variations", json={"content": {"variations": []}})
    vt.data.plans("glo", sme=True)
    assert "serviceID=glo-sme-data" in api.calls[0].request.url


def test_synced_catalogue_is_used_without_api_calls(api, vt, funded_user):
    from django.utils import timezone

    category = ServiceCategory.objects.create(identifier="data", name="Data")
    service = Service.objects.create(category=category, service_id="mtn-data", name="MTN Data",
                                     variations_synced_at=timezone.now())
    Variation.objects.create(service=service, variation_code="mtn-1gb", name="1GB", amount=Decimal("299"))
    assert vt.data.plans("mtn")[0]["variation_amount"] == "299.00"
    assert len(api.calls) == 0
    api.post(BASE + "pay", json=pay_body())
    assert vt.data.buy("08031234567", "mtn-1gb", user=funded_user).amount == Decimal("299.00")
