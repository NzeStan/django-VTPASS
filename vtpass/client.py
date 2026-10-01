"""
Low-level HTTP client for the VTpass Billing API.

This module has no database dependency: it can be used on its own from a
script, a Celery worker or a non-Django service. Higher-level flows (pricing,
wallets, persistence, signals) live in :mod:`vtpass.services`.

    from vtpass.client import VTpassClient

    client = VTpassClient()               # reads settings.VTPASS
    client.get_balance()
    client.get_variations("mtn-data")
    client.verify("ikeja-electric", "1111111111111", type="prepaid")
    client.pay(serviceID="mtn", amount=100, phone="08011111111")
    client.requery("202501011230abcd...")

Thread safety: each thread gets its own pooled ``requests.Session``.
"""

import base64
import threading
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from vtpass import __version__
from vtpass.constants import ResponseCode, Status, VTpassTransactionStatus
from vtpass.exceptions import (
    VTpassAPIError,
    VTpassAuthenticationError,
    VTpassConfigError,
    VTpassMerchantError,
    VTpassNetworkError,
    VTpassValidationError,
)
from vtpass.logger import log_request, log_response
from vtpass.settings import vtpass_settings
from vtpass.utils import first_present, generate_request_id, to_decimal

# ----------------------------------------------------------------------------- responses
_TXN_STATUS_MAP = {
    VTpassTransactionStatus.DELIVERED: Status.SUCCESSFUL,
    VTpassTransactionStatus.PENDING: Status.PENDING,
    VTpassTransactionStatus.INITIATED: Status.PENDING,
    VTpassTransactionStatus.FAILED: Status.FAILED,
    VTpassTransactionStatus.REVERSED: Status.REVERSED,
}


def resolve_status(code, transaction_status=None):
    """
    Map a VTpass ``code`` + ``content.transactions.status`` to a package :class:`Status`.

    The rule is conservative: only an explicit ``delivered`` is success and
    only explicit failures are failures. Anything ambiguous stays PENDING and
    is settled later by requery, so money is never refunded for a delivered
    product nor kept for a failed one.
    """
    code = str(code or "")
    txn_status = (transaction_status or "").lower()
    if code == ResponseCode.TRANSACTION_REVERSAL or txn_status == VTpassTransactionStatus.REVERSED:
        return Status.REVERSED
    if txn_status in _TXN_STATUS_MAP:
        return _TXN_STATUS_MAP[txn_status]
    if code in (ResponseCode.PROCESSED, ResponseCode.TRANSACTION_QUERY, ResponseCode.TRANSACTION_RESOLVED):
        return Status.PENDING
    if code in ResponseCode.PENDING_CODES or not code:
        return Status.PENDING
    return Status.FAILED


@dataclass
class VTpassResponse:
    """Normalised view over any Billing API response."""

    raw: Dict[str, Any]
    http_status: int = 200
    elapsed: float = 0.0

    # ---- generic ----------------------------------------------------------------
    @property
    def code(self) -> str:
        return str(self.raw.get("code", "") or "")

    @property
    def description(self) -> str:
        return str(self.raw.get("response_description", "") or "")

    @property
    def content(self):
        content = self.raw.get("content")
        if content is None:
            content = self.raw.get("contents")
        return content if content is not None else {}

    @property
    def ok(self) -> bool:
        return self.code == ResponseCode.PROCESSED or self.description == ResponseCode.PROCESSED

    @property
    def error_message(self) -> Optional[str]:
        content = self.content
        if isinstance(content, dict) and content.get("error"):
            return str(content["error"])
        if isinstance(content, dict) and content.get("errors"):
            return str(content["errors"])
        if not self.ok and self.description and self.description != ResponseCode.PROCESSED:
            return self.description
        return None

    # ---- transaction fields --------------------------------------------------------
    @property
    def transaction(self) -> Dict[str, Any]:
        content = self.content
        if isinstance(content, dict) and isinstance(content.get("transactions"), dict):
            return content["transactions"]
        return {}

    @property
    def transaction_status(self) -> str:
        return str(self.transaction.get("status", "") or "")

    @property
    def status(self) -> str:
        return resolve_status(self.code, self.transaction_status)

    @property
    def request_id(self) -> Optional[str]:
        return self.raw.get("requestId") or self.raw.get("request_id")

    @property
    def vtpass_transaction_id(self) -> Optional[str]:
        value = self.transaction.get("transactionId")
        return str(value) if value else None

    @property
    def amount(self) -> Optional[Decimal]:
        return to_decimal(self.transaction.get("amount", self.raw.get("amount")))

    @property
    def total_amount(self) -> Optional[Decimal]:
        """What VTpass actually debited from your merchant wallet."""
        return to_decimal(self.transaction.get("total_amount"))

    @property
    def commission(self) -> Optional[Decimal]:
        details = self.transaction.get("commission_details") or {}
        return to_decimal(details.get("amount"), to_decimal(self.transaction.get("commission")))

    @property
    def commission_details(self) -> Dict[str, Any]:
        return self.transaction.get("commission_details") or {}

    @property
    def convenience_fee(self) -> Optional[Decimal]:
        return to_decimal(self.transaction.get("convinience_fee"))

    # ---- vended value -------------------------------------------------------------
    @property
    def purchased_code(self) -> str:
        return str(self.raw.get("purchased_code") or self.raw.get("Pin") or "")

    @property
    def token(self) -> Optional[str]:
        """Prepaid electricity token, when present."""
        value = first_present(
            self.raw, "token", "mainToken", "Token", "purchased_code"
        ) or first_present(self.transaction, "token", "mainToken")
        if value and isinstance(value, str) and value.lower().startswith("token"):
            value = value.split(":", 1)[-1].strip()
        return str(value) if value else None

    @property
    def units(self) -> Optional[str]:
        value = first_present(self.raw, "units", "Units", "mainTokenUnits", "PurchasedUnits")
        return str(value) if value else None

    @property
    def vend_details(self) -> Dict[str, Any]:
        """
        Everything the customer needs after a successful purchase in one dict:
        electricity token/units, exam PINs and serials, Showmax vouchers,
        Spectranet cards, insurance certificate link, etc.
        """
        keys = (
            "purchased_code", "token", "mainToken", "Token", "units", "Units", "mainTokenUnits",
            "tokenAmount", "mainTokenAmount", "bonusToken", "bonusTokenUnits", "exchangeReference",
            "customerName", "CustomerName", "customerAddress", "address", "meterNumber",
            "tariff", "taxAmount", "debtAmount", "kct1", "kct2", "Pin", "pin", "cards", "tokens",
            "Voucher", "certUrl", "certificateUrl", "ExpiryDate", "Serial",
        )
        details = {key: self.raw[key] for key in keys if self.raw.get(key) not in (None, "", [])}
        for key in ("cards", "tokens", "Voucher", "certUrl"):
            value = self.transaction.get(key)
            if value not in (None, "", []) and key not in details:
                details[key] = value
        return details

    def to_dict(self):
        return dict(self.raw)


# ----------------------------------------------------------------------------- http base
class BaseHTTPClient:
    """Shared plumbing: thread-local pooled sessions, retries, timeouts, logging."""

    def __init__(self, base_url, timeout=None, verify_ssl=None, max_retries=None, backoff=None):
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self.timeout = timeout or vtpass_settings.timeout
        self.verify_ssl = vtpass_settings.VERIFY_SSL if verify_ssl is None else verify_ssl
        self.max_retries = vtpass_settings.MAX_RETRIES if max_retries is None else max_retries
        self.backoff = vtpass_settings.RETRY_BACKOFF if backoff is None else backoff
        self._local = threading.local()

    @property
    def session(self) -> requests.Session:
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            retry = Retry(
                total=self.max_retries,
                connect=self.max_retries,
                read=self.max_retries,
                status=self.max_retries,
                backoff_factor=self.backoff,
                status_forcelist=(429, 502, 503, 504),
                allowed_methods=frozenset({"GET"}),  # never auto-retry POST
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=50)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
            session.verify = self.verify_ssl
            session.headers["User-Agent"] = (
                vtpass_settings.USER_AGENT or f"django-vtpass/{__version__}"
            )
            self._local.session = session
        return session

    def url(self, path):
        return self.base_url + path.lstrip("/")

    def _send(self, method, path, headers, params=None, json=None, data=None):
        url = self.url(path)
        log_request(method, url, json or data or params)
        started = time.monotonic()
        try:
            response = self.session.request(
                method, url, headers=headers, params=params, json=json, data=data,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise VTpassNetworkError(
                "VTpass did not respond in time.", original_error=exc, timeout=True
            ) from exc
        except requests.RequestException as exc:
            raise VTpassNetworkError(f"Could not reach VTpass: {exc}", original_error=exc) from exc
        elapsed = time.monotonic() - started
        return response, elapsed


# ----------------------------------------------------------------------------- billing
class VTpassClient(BaseHTTPClient):
    """Client for ``https://vtpass.com/api/`` (or the sandbox)."""

    def __init__(
        self,
        api_key=None,
        public_key=None,
        secret_key=None,
        username=None,
        password=None,
        auth_method=None,
        sandbox=None,
        base_url=None,
        **kwargs,
    ):
        settings = vtpass_settings
        self.api_key = api_key if api_key is not None else settings.API_KEY
        self.public_key = public_key if public_key is not None else settings.PUBLIC_KEY
        self.secret_key = secret_key if secret_key is not None else settings.SECRET_KEY
        self.username = username if username is not None else settings.USERNAME
        self.password = password if password is not None else settings.PASSWORD
        self.auth_method = auth_method or settings.AUTH_METHOD
        if base_url is None:
            if sandbox is None:
                base_url = settings.base_url
            else:
                from vtpass.settings import LIVE_BASE_URL, SANDBOX_BASE_URL

                base_url = SANDBOX_BASE_URL if sandbox else LIVE_BASE_URL
        super().__init__(base_url, **kwargs)

    # ---- auth ---------------------------------------------------------------------
    def _headers(self, method):
        headers = {"Accept": "application/json"}
        if self.auth_method == "basic":
            if not (self.username and self.password):
                raise VTpassConfigError("VTPASS USERNAME/PASSWORD are required for basic auth.")
            token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            headers["Authorization"] = f"Basic {token}"
            return headers
        if not self.api_key:
            raise VTpassConfigError("VTPASS['API_KEY'] is not configured.")
        headers["api-key"] = self.api_key
        if method == "GET":
            if not self.public_key:
                raise VTpassConfigError("VTPASS['PUBLIC_KEY'] is not configured.")
            headers["public-key"] = self.public_key
        else:
            if not self.secret_key:
                raise VTpassConfigError("VTPASS['SECRET_KEY'] is not configured.")
            headers["secret-key"] = self.secret_key
        return headers

    # ---- transport ------------------------------------------------------------------
    def request(self, method, path, params=None, payload=None, raise_for_code=True):
        method = method.upper()
        response, elapsed = self._send(
            method, path, self._headers(method), params=params, json=payload
        )
        try:
            body = response.json()
        except ValueError:
            body = None
        log_response(method, response.url, response.status_code, body, elapsed)

        if response.status_code in (401, 403):
            raise VTpassAuthenticationError(
                "VTpass rejected the API credentials.", status_code=response.status_code,
                response=body or response.text,
            )
        if body is None or not isinstance(body, (dict, list)):
            raise VTpassAPIError(
                f"Unexpected response from VTpass (HTTP {response.status_code}).",
                status_code=response.status_code, response=response.text[:2000],
            )
        if isinstance(body, list):
            body = {"code": ResponseCode.PROCESSED, "content": body}
        result = VTpassResponse(raw=body, http_status=response.status_code, elapsed=elapsed)
        if response.status_code >= 500 and not result.code:
            raise VTpassAPIError(
                f"VTpass server error (HTTP {response.status_code}).",
                status_code=response.status_code, response=body,
            )
        if result.code == ResponseCode.INVALID_CREDENTIALS:
            raise VTpassAuthenticationError(
                result.description or "Invalid credentials", code=result.code, response=body
            )
        if raise_for_code:
            self.raise_for_code(result)
        return result

    @staticmethod
    def raise_for_code(result: VTpassResponse):
        """Raise for lookup/verification responses that did not succeed."""
        code = result.code
        if code in ("", ResponseCode.PROCESSED, ResponseCode.BILLER_CONFIRMED, "1"):
            if result.error_message and isinstance(result.content, dict) and result.content.get("error"):
                raise VTpassValidationError(result.error_message, code=code, response=result.raw)
            return
        message = result.error_message or ResponseCode.DESCRIPTIONS.get(code, "VTpass error")
        if code in ResponseCode.MERCHANT_ERROR_CODES:
            raise VTpassMerchantError(message, code=code, response=result.raw)
        if code in (
            ResponseCode.INVALID_ARGUMENTS, ResponseCode.PRODUCT_NOT_FOUND,
            ResponseCode.VARIATION_CODE_NOT_FOUND, ResponseCode.BELOW_MINIMUM_AMOUNT,
            ResponseCode.ABOVE_MAXIMUM_AMOUNT, ResponseCode.BELOW_MINIMUM_QUANTITY,
            ResponseCode.ABOVE_MAXIMUM_QUANTITY,
        ):
            raise VTpassValidationError(message, code=code, response=result.raw)
        raise VTpassAPIError(message, code=code, response=result.raw)

    def get(self, path, params=None, **kwargs):
        return self.request("GET", path, params=params, **kwargs)

    def post(self, path, payload=None, **kwargs):
        return self.request("POST", path, payload=payload, **kwargs)

    # ---- account --------------------------------------------------------------------
    def get_balance(self) -> Decimal:
        """Your VTpass merchant wallet balance."""
        result = self.get("balance", raise_for_code=False)
        content = result.content if isinstance(result.content, dict) else {}
        balance = to_decimal(content.get("balance"))
        if balance is None:
            raise VTpassAPIError("Could not read the VTpass balance.", response=result.raw)
        return balance

    # ---- catalogue ------------------------------------------------------------------
    def get_service_categories(self) -> List[Dict[str, Any]]:
        return _as_list(self.get("service-categories").content)

    def get_services(self, identifier) -> List[Dict[str, Any]]:
        """Services in a category, e.g. ``identifier="data"``."""
        return _as_list(self.get("services", params={"identifier": identifier}).content)

    def get_variations(self, service_id, **extra_params) -> Dict[str, Any]:
        """
        Plans/bouquets for a service. Returns the ``content`` dict with a
        normalised ``variations`` list (VTpass sometimes spells it ``varations``).
        Extra params are forwarded (international airtime needs ``operator_id``
        and ``product_type_id``).
        """
        params = {"serviceID": service_id, **extra_params}
        content = self.get("service-variations", params=params).content or {}
        if isinstance(content, dict):
            content = dict(content)
            content["variations"] = content.get("variations") or content.get("varations") or []
        return content

    def get_options(self, service_id, name) -> Dict[str, Any]:
        """Product options API (``/api/options?serviceID=...&name=...``)."""
        return self.get("options", params={"serviceID": service_id, "name": name}).content

    # ---- verification ---------------------------------------------------------------
    def verify(self, service_id, billers_code, type=None, **extra) -> Dict[str, Any]:
        """
        Verify a customer before payment (``merchant-verify``): meter numbers
        (``type`` = prepaid/postpaid), smartcards/IUCs, JAMB profile IDs
        (``type`` = variation code), Smile account IDs, etc.

        Returns the ``content`` dict (``Customer_Name``, ``Address``,
        ``Renewal_Amount``, ``Current_Bouquet``...). Raises
        :class:`VTpassValidationError` when the number is invalid.
        """
        payload = {"billersCode": str(billers_code), "serviceID": service_id, **extra}
        if type:
            payload["type"] = type
        result = self.post("merchant-verify", payload)
        content = result.content if isinstance(result.content, dict) else {}
        if content.get("error") or content.get("WrongBillersCode"):
            raise VTpassValidationError(
                str(content.get("error") or "Invalid customer number."),
                code=result.code, response=result.raw,
            )
        return content

    def verify_smile_email(self, email) -> Dict[str, Any]:
        """Look up a Smile account by email (returns the account list)."""
        result = self.post("merchant-verify/smile/email", {"billersCode": email, "serviceID": "smile-direct"})
        content = result.content if isinstance(result.content, dict) else {}
        if content.get("error"):
            raise VTpassValidationError(str(content["error"]), code=result.code, response=result.raw)
        return content

    # ---- payments -------------------------------------------------------------------
    def pay(self, request_id=None, **payload) -> VTpassResponse:
        """
        POST ``/api/pay``. Pass VTpass field names as keyword args
        (``serviceID``, ``amount``, ``phone``, ``billersCode``, ``variation_code``,
        ``subscription_type``, ``quantity`` ...). Returns the response without
        raising for business failures; inspect ``response.status``.

        Network errors propagate as :class:`VTpassNetworkError`; callers must
        then treat the purchase as *pending* and requery – never as failed.
        """
        payload["request_id"] = request_id or payload.get("request_id") or generate_request_id()
        clean = {k: v for k, v in payload.items() if v not in (None, "")}
        if "amount" in clean:
            clean["amount"] = _plain_number(clean["amount"])
        return self.post("pay", clean, raise_for_code=False)

    def requery(self, request_id, retries=2) -> VTpassResponse:
        """Fetch the latest status of a purchase. Safe to retry; it is read-only."""
        attempt = 0
        while True:
            try:
                return self.post("requery", {"request_id": request_id}, raise_for_code=False)
            except VTpassNetworkError:
                attempt += 1
                if attempt > retries:
                    raise
                time.sleep(self.backoff * (2 ** attempt))

    # ---- international airtime ------------------------------------------------------
    def get_international_countries(self) -> List[Dict[str, Any]]:
        content = self.get("get-international-airtime-countries").content
        return _as_list(content.get("countries") if isinstance(content, dict) else content)

    def get_international_product_types(self, country_code) -> List[Dict[str, Any]]:
        return _as_list(
            self.get("get-international-airtime-product-types", params={"code": country_code}).content
        )

    def get_international_operators(self, country_code, product_type_id) -> List[Dict[str, Any]]:
        return _as_list(
            self.get(
                "get-international-airtime-operators",
                params={"code": country_code, "product_type_id": product_type_id},
            ).content
        )

    def get_international_variations(self, operator_id, product_type_id) -> Dict[str, Any]:
        return self.get_variations(
            "foreign-airtime", operator_id=operator_id, product_type_id=product_type_id
        )

    # ---- insurance ------------------------------------------------------------------
    def get_insurance_options(self, option, parent=None):
        """
        Universal Insurance (third-party motor) lookups: ``color``,
        ``engine-capacity``, ``state``, ``lga`` (parent = state code),
        ``brand`` and ``model`` (parent = vehicle make code).
        """
        path = f"universal-insurance/options/{option}"
        if parent not in (None, ""):
            path += f"/{parent}"
        return self.get(path).content


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("data", "items", "content"):
            if isinstance(value.get(key), list):
                return value[key]
        return [value]
    return [value]


def _plain_number(value):
    number = to_decimal(value)
    if number is None:
        return value
    if number == number.to_integral_value():
        return int(number)
    return float(number)
