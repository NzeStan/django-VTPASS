import json

import pytest

from tests.conftest import BASE, pay_body
from vtpass.exceptions import VTpassValidationError

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "phone,service_id",
    [("08031234567", "mtn"), ("08021234567", "airtel"), ("08051234567", "glo"), ("08091234567", "etisalat")],
)
def test_network_auto_detection(api, vt, funded_user, phone, service_id):
    api.post(BASE + "pay", json=pay_body())
    txn = vt.airtime.buy(phone, 100, user=funded_user)
    assert txn.service_id == service_id
    assert json.loads(api.calls[0].request.body)["serviceID"] == service_id


def test_explicit_network_overrides_prefix(api, vt, funded_user):
    """Ported numbers keep their old prefix, so the customer's choice wins."""
    api.post(BASE + "pay", json=pay_body())
    assert vt.airtime.buy("08031234567", 100, network="glo", user=funded_user).service_id == "glo"
    assert vt.airtime.buy("08031234567", 100, network="etisalat", user=funded_user).service_id == "etisalat"


def test_undetectable_network_requires_choice(vt, funded_user):
    with pytest.raises(VTpassValidationError):
        vt.airtime.buy("08011111111", 100, user=funded_user)


def test_networks_listing(vt):
    assert {n["service_id"] for n in vt.airtime.networks()} == {"mtn", "glo", "airtel", "etisalat"}


def test_unknown_network(vt, funded_user):
    with pytest.raises(VTpassValidationError):
        vt.airtime.buy("08031234567", 100, network="ntel", user=funded_user)
