"""Helpers shared across the package (request IDs, phone numbers, money, masking)."""

import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    from backports.zoneinfo import ZoneInfo  # type: ignore

from django.utils.crypto import get_random_string

from vtpass.constants import Network

LAGOS = ZoneInfo("Africa/Lagos")
_REQUEST_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
TWO_PLACES = Decimal("0.01")


# --------------------------------------------------------------------------- IDs
def generate_request_id(suffix_length=None, now=None):
    """
    Build a VTpass ``request_id``.

    VTpass requires the first 12 characters to be the current Africa/Lagos
    date-time as ``YYYYMMDDHHMM`` followed by any alphanumeric suffix. The
    suffix uses a cryptographically secure random string so IDs cannot be
    guessed or collide across processes.
    """
    from vtpass.settings import vtpass_settings

    length = suffix_length if suffix_length is not None else vtpass_settings.REQUEST_ID_SUFFIX_LENGTH
    stamp = (now or datetime.now(tz=LAGOS)).astimezone(LAGOS).strftime("%Y%m%d%H%M")
    return stamp + get_random_string(max(int(length), 4), _REQUEST_ID_CHARS)


REQUEST_ID_RE = re.compile(r"^\d{12}[A-Za-z0-9_-]*$")


def is_valid_request_id(value):
    return bool(value) and bool(REQUEST_ID_RE.match(str(value)))


# ------------------------------------------------------------------- phone numbers
NETWORK_PREFIXES = {
    Network.MTN: (
        "0803", "0806", "0703", "0706", "0810", "0813", "0814", "0816", "0903",
        "0906", "0913", "0916", "0704", "07025", "07026",
    ),
    Network.AIRTEL: (
        "0802", "0808", "0708", "0812", "0701", "0902", "0907", "0901", "0904",
        "0912", "0911",
    ),
    Network.GLO: ("0805", "0807", "0705", "0815", "0811", "0905", "0915"),
    Network.NINE_MOBILE: ("0809", "0818", "0817", "0909", "0908"),
}


def normalize_phone(phone):
    """
    Normalise a Nigerian phone number to the local 11-digit format (``080...``).

    Accepts ``+234...``, ``234...``, ``0...`` and 10-digit numbers without the
    leading zero. Non-Nigerian or unusual numbers are returned digits-only so
    international flows keep working.
    """
    if phone is None:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if digits.startswith("234") and len(digits) == 13:
        return "0" + digits[3:]
    if len(digits) == 10 and digits[0] in "789":
        return "0" + digits
    return digits


def to_international(phone):
    local = normalize_phone(phone)
    if len(local) == 11 and local.startswith("0"):
        return "234" + local[1:]
    return local


def is_valid_nigerian_phone(phone):
    local = normalize_phone(phone)
    return len(local) == 11 and local[:2] in ("07", "08", "09")


def detect_network(phone):
    """
    Guess the network from the number prefix, like OPay/PalmPay do.

    This is a hint only: ported numbers keep their old prefix. Returns a
    :class:`~vtpass.constants.Network` value or ``None``.
    """
    local = normalize_phone(phone)
    if len(local) != 11:
        return None
    # Longest prefixes first so 5-digit ranges win over 4-digit ones.
    matches = [
        (len(prefix), network)
        for network, prefixes in NETWORK_PREFIXES.items()
        for prefix in prefixes
        if local.startswith(prefix)
    ]
    if not matches:
        return None
    return max(matches, key=lambda item: item[0])[1]


# --------------------------------------------------------------------------- money
def to_decimal(value, default=None):
    if value is None or value == "":
        return default
    if isinstance(value, Decimal):
        return value
    try:
        # str() first so floats like 0.1 do not leak binary noise.
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return default


def quantize(value):
    return to_decimal(value, Decimal("0")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def compute_amount(base, amount_type, value, cap=None, minimum=None):
    """Apply a flat or percentage charge to ``base`` with an optional cap and floor."""
    value = to_decimal(value, Decimal("0"))
    if not value:
        return Decimal("0.00")
    if amount_type == "percent":
        result = to_decimal(base, Decimal("0")) * value / Decimal("100")
    else:
        result = value
    cap = to_decimal(cap)
    minimum = to_decimal(minimum)
    if cap is not None and result > cap:
        result = cap
    if minimum is not None and result < minimum:
        result = minimum
    return quantize(result)


# ------------------------------------------------------------------------- masking
SENSITIVE_KEYS = {
    "api-key", "api_key", "secret-key", "secret_key", "public-key", "public_key",
    "x-token", "x-secret", "authorization", "password", "pin", "token", "tokens",
    "purchased_code", "maintoken", "cards", "voucher", "certurl",
}


def mask_value(value, visible=4):
    text = str(value)
    if len(text) <= visible:
        return "*" * len(text)
    return "*" * (len(text) - visible) + text[-visible:]


def mask_data(data):
    """Recursively mask secrets and vended codes before logging."""
    if isinstance(data, dict):
        return {
            key: (mask_value(value) if str(key).lower() in SENSITIVE_KEYS and value not in (None, "")
                  else mask_data(value))
            for key, value in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [mask_data(item) for item in data]
    return data


def get_client_ip(request, header=None):
    if header:
        forwarded = request.META.get(header)
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def first_present(mapping, *keys, default=None):
    """Return the first non-empty value found under any of ``keys`` (case-insensitive)."""
    if not isinstance(mapping, dict):
        return default
    lowered = {str(k).lower(): v for k, v in mapping.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, "", [], {}):
            return value
    return default
