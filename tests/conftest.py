from decimal import Decimal

import pytest
import responses
from django.contrib.auth import get_user_model
from django.core.cache import cache

BASE = "https://sandbox.vtpass.com/api/"
SMS_BASE = "https://messaging.vtpass.com/"


def pay_body(status="delivered", code="000", amount=100, total_amount=None, commission=None,
             description="TRANSACTION SUCCESSFUL", **extra):
    transactions = {
        "status": status,
        "product_name": extra.pop("product_name", "MTN Airtime VTU"),
        "unique_element": "08011111111",
        "amount": amount,
        "transactionId": extra.pop("transaction_id", "17415980564672211596777904"),
    }
    if total_amount is not None:
        transactions["total_amount"] = total_amount
    if commission is not None:
        transactions["commission"] = commission
        transactions["commission_details"] = {"amount": commission, "rate": "3.00", "rate_type": "percent"}
    body = {
        "code": code,
        "response_description": description,
        "content": {"transactions": transactions},
        "requestId": extra.pop("request_id", "202501011200abc"),
        "amount": amount,
    }
    body.update(extra)
    return body


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield mock


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user("ada", "ada@example.com", "pass")


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user("bayo", "bayo@example.com", "pass")


@pytest.fixture
def staff(db):
    return get_user_model().objects.create_superuser("admin", "admin@example.com", "pass")


@pytest.fixture
def wallet_backend():
    from vtpass.wallets import ModelWalletBackend

    return ModelWalletBackend()


@pytest.fixture
def funded_user(user, wallet_backend):
    wallet_backend.credit(user, Decimal("10000"), reference="fund-1")
    return user


@pytest.fixture
def vt():
    from vtpass.services import VTpass

    return VTpass()


@pytest.fixture
def mtn_data_variations(api):
    api.get(
        BASE + "service-variations",
        json={
            "response_description": "000",
            "content": {
                "ServiceName": "MTN Data",
                "serviceID": "mtn-data",
                "convinience_fee": "0 %",
                "varations": [
                    {"variation_code": "mtn-1gb", "name": "MTN 1GB", "variation_amount": "300.00", "fixedPrice": "Yes"},
                    {"variation_code": "mtn-2gb", "name": "MTN 2GB", "variation_amount": "600.00", "fixedPrice": "Yes"},
                ],
            },
        },
    )
    return api
