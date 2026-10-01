from decimal import Decimal

import pytest

from vtpass.constants import Network
from vtpass.utils import (
    compute_amount,
    detect_network,
    is_valid_nigerian_phone,
    mask_data,
    normalize_phone,
    to_decimal,
    to_international,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("08031234567", "08031234567"),
        ("+2348031234567", "08031234567"),
        ("2348031234567", "08031234567"),
        ("8031234567", "08031234567"),
        ("0803 123 4567", "08031234567"),
        (None, ""),
    ],
)
def test_normalize_phone(raw, expected):
    assert normalize_phone(raw) == expected


def test_international_format_and_validation():
    assert to_international("08031234567") == "2348031234567"
    assert is_valid_nigerian_phone("+2347061234567")
    assert not is_valid_nigerian_phone("0601234567")


@pytest.mark.parametrize(
    "phone,network",
    [
        ("08031234567", Network.MTN),
        ("07025123456", Network.MTN),
        ("08021234567", Network.AIRTEL),
        ("09121234567", Network.AIRTEL),
        ("08051234567", Network.GLO),
        ("09151234567", Network.GLO),
        ("08091234567", Network.NINE_MOBILE),
        ("08011111111", None),
        ("123", None),
    ],
)
def test_detect_network(phone, network):
    assert detect_network(phone) == network


def test_compute_amount():
    assert compute_amount(Decimal("1000"), "percent", "2") == Decimal("20.00")
    assert compute_amount(Decimal("100000"), "percent", "2", cap="500") == Decimal("500.00")
    assert compute_amount(Decimal("100"), "percent", "1", minimum="10") == Decimal("10.00")
    assert compute_amount(Decimal("1000"), "flat", "100") == Decimal("100.00")
    assert compute_amount(Decimal("1000"), "flat", None) == Decimal("0.00")


def test_to_decimal_avoids_float_noise():
    assert to_decimal(0.1) == Decimal("0.1")
    assert to_decimal("1,250.50") == Decimal("1250.50")
    assert to_decimal("abc") is None


def test_mask_data_hides_secrets_and_vended_codes():
    masked = mask_data({"api-key": "abcdef123456", "nested": [{"purchased_code": "TOKEN12345678"}], "phone": "080"})
    assert masked["api-key"].endswith("3456") and "abcdef" not in masked["api-key"]
    assert "TOKEN1234" not in masked["nested"][0]["purchased_code"]
    assert masked["phone"] == "080"
