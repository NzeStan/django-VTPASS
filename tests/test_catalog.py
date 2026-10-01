import pytest

from tests.conftest import BASE
from vtpass.models import Service, ServiceCategory, Variation

pytestmark = pytest.mark.django_db


def mock_catalog(api, services):
    api.get(BASE + "service-categories", json={"response_description": "000", "content": [
        {"identifier": "airtime", "name": "Airtime Recharge"},
        {"identifier": "data", "name": "Data Services"},
    ]})
    api.get(BASE + "services?identifier=airtime", json={"response_description": "000", "content": [
        {"serviceID": "mtn", "name": "MTN Airtime VTU", "minimium_amount": "50", "maximum_amount": 200000,
         "convinience_fee": "0 %", "product_type": "flexible", "image": "https://x/mtn.jpg"},
    ]})
    api.get(BASE + "services?identifier=data", json={"response_description": "000", "content": services})
    api.get(BASE + "service-variations?serviceID=mtn", json={"content": {"variations": []}})
    api.get(BASE + "service-variations?serviceID=mtn-data", json={"content": {"varations": [
        {"variation_code": "mtn-1gb", "name": "1GB", "variation_amount": "300", "fixedPrice": "Yes"},
    ]}})
    api.get(BASE + "service-variations?serviceID=glo-data", json={"content": {"variations": []}})


def test_sync_creates_catalogue(api, vt):
    mock_catalog(api, [{"serviceID": "mtn-data", "name": "MTN Data"}, {"serviceID": "glo-data", "name": "Glo Data"}])
    stats = vt.catalog.sync()
    assert stats == {"categories": 2, "services": 3, "variations": 1}
    mtn = Service.objects.get(service_id="mtn")
    assert str(mtn.minimum_amount) == "50.00" and str(mtn.maximum_amount) == "200000.00"
    assert Variation.objects.get().variation_code == "mtn-1gb"
    assert vt.catalog.categories()[0]["identifier"] == "airtime"


def test_sync_deactivates_removed_items(api, vt):
    mock_catalog(api, [{"serviceID": "mtn-data", "name": "MTN Data"}, {"serviceID": "glo-data", "name": "Glo Data"}])
    vt.catalog.sync()
    api.reset()
    mock_catalog(api, [{"serviceID": "mtn-data", "name": "MTN Data"}])
    vt.catalog.sync()
    assert not Service.objects.get(service_id="glo-data").is_active
    assert ServiceCategory.objects.count() == 2


def test_sync_only_selected_categories(api, vt):
    mock_catalog(api, [])
    stats = vt.catalog.sync(categories=["airtime"], with_variations=False)
    assert stats["categories"] == 1 and stats["variations"] == 0
