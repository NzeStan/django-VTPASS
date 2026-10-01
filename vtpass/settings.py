"""
Package configuration.

All configuration lives in a single ``VTPASS`` dict in your Django settings.
Every key is optional; nested dicts are merged with the defaults below, so you
only write what you want to change. Values are read lazily (never at import
time) and are reloaded automatically when tests use ``override_settings``.

    from vtpass.settings import vtpass_settings
    vtpass_settings.SANDBOX
    vtpass_settings.WEBHOOK["TOKEN"]
"""

import copy
import logging

from django.conf import settings as django_settings
from django.core.signals import setting_changed
from django.utils.module_loading import import_string

from vtpass.exceptions import VTpassConfigError

SANDBOX_BASE_URL = "https://sandbox.vtpass.com/api/"
LIVE_BASE_URL = "https://vtpass.com/api/"
MESSAGING_BASE_URL = "https://messaging.vtpass.com/"

DEFAULTS = {
    # --- Billing API credentials -------------------------------------------
    # Get these from vtpass.com/account (or sandbox.vtpass.com/account) > API Keys.
    "API_KEY": "",
    "PUBLIC_KEY": "",
    "SECRET_KEY": "",
    # Legacy basic auth (VTpass email/password). Used when AUTH_METHOD="basic".
    "USERNAME": "",
    "PASSWORD": "",
    "AUTH_METHOD": "api_key",  # "api_key" | "basic"
    "SANDBOX": True,
    "BASE_URL": None,  # override the environment URL (e.g. for a proxy)
    # --- HTTP ----------------------------------------------------------------
    "CONNECT_TIMEOUT": 10,
    "READ_TIMEOUT": 60,
    "VERIFY_SSL": True,
    # Retries apply to safe reads only. Purchases are NEVER retried blindly:
    # an unanswered purchase is left pending and resolved with requery.
    "MAX_RETRIES": 3,
    "RETRY_BACKOFF": 0.5,
    "USER_AGENT": None,
    # --- Request IDs -----------------------------------------------------------
    "REQUEST_ID_SUFFIX_LENGTH": 12,
    # --- Messaging (bulk SMS) ------------------------------------------------
    "MESSAGING": {
        "PUBLIC_KEY": "",  # X-Token  (VT_PK_...)
        "SECRET_KEY": "",  # X-Secret (VT_SK_...)
        "BASE_URL": MESSAGING_BASE_URL,
        "DEFAULT_SENDER": "",
        "DEFAULT_ROUTE": "normal",  # normal | dnd | dnd-fallback | simhost | simhost-fallback
        "API_VERSION": 2,  # 1 = GET endpoints, 2 = POST endpoints (where available)
        "LOG_MESSAGES": True,  # keep an SMSMessage record of every send
    },
    # --- Money -------------------------------------------------------------
    # Dotted path to a wallet backend, or None to collect payment yourself
    # (card, transfer...) and only use the package for vending.
    "WALLET_BACKEND": None,  # e.g. "vtpass.wallets.ModelWalletBackend"
    "PRICING_BACKEND": "vtpass.pricing.RuleBasedPricing",
    # Code-defined pricing rules (same fields as the PricingRule model).
    # Database rules take precedence over these.
    "PRICING_RULES": [],
    "CASHBACK_ENABLED": True,
    "CURRENCY": "NGN",
    "LIMITS": {
        "MIN_AMOUNT": None,
        "MAX_AMOUNT": None,
        "DAILY_AMOUNT_PER_USER": None,
        "DAILY_COUNT_PER_USER": None,
    },
    # --- Catalogue -----------------------------------------------------------
    "CATALOG_CACHE_TIMEOUT": 60 * 60,
    # --- Pending transaction resolution ------------------------------------
    "REQUERY": {
        # Seconds to wait before each successive requery of a pending transaction.
        "SCHEDULE": [30, 60, 120, 300, 600, 1800, 3600, 3600, 3600, 7200],
        # VTpass answers 015 (unknown request id) when a purchase never arrived.
        # After this many minutes such a transaction is marked failed.
        "FAIL_UNKNOWN_AFTER_MINUTES": 10,
        "BATCH_SIZE": 100,
    },
    # --- Webhooks ------------------------------------------------------------
    "WEBHOOK": {
        # Shared secret placed in the callback URL you register on VTpass,
        # e.g. https://api.example.com/vtpass/webhook/<TOKEN>/ . VTpass does not
        # sign callbacks, so the token (and optionally an IP allowlist) is how
        # you reject forged requests.
        "TOKEN": "",
        "ALLOWED_IPS": [],
        # Never trust the payload for money movement: confirm with requery.
        "VERIFY_WITH_REQUERY": True,
        "STORE_EVENTS": True,
    },
    # Request header holding the real client IP when running behind a trusted
    # proxy/load balancer (e.g. "HTTP_X_FORWARDED_FOR"). Used for the webhook
    # IP allowlist and for recording the client IP of purchases.
    "TRUSTED_IP_HEADER": None,
    # --- Async ---------------------------------------------------------------
    "USE_CELERY": False,
    "CELERY_QUEUE": None,
    # --- Notifications -------------------------------------------------------
    "NOTIFICATIONS": {
        "ENABLED": False,
        # Dotted paths; see vtpass.notifications.backends.
        "BACKENDS": [],
        # Which events trigger notifications.
        "EVENTS": ["transaction.successful", "transaction.failed", "transaction.reversed"],
        "SMS_SENDER": None,  # defaults to MESSAGING.DEFAULT_SENDER
        "SMS_ROUTE": None,
        "EMAIL_FROM": None,  # defaults to DEFAULT_FROM_EMAIL
        "TEMPLATES": {},  # event -> {"subject": ..., "body": ...} overrides
        "ASYNC": True,  # use Celery when USE_CELERY is True
    },
    # --- Merchant monitoring -----------------------------------------------
    "LOW_BALANCE_THRESHOLD": None,  # emits merchant_balance_low below this amount
    # --- REST API (optional, needs djangorestframework) --------------------
    "API": {
        "PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
        "ADMIN_PERMISSION_CLASSES": ["rest_framework.permissions.IsAdminUser"],
        "PURCHASE_THROTTLE_RATE": "30/min",
        "VERIFY_THROTTLE_RATE": "60/min",
        "ALLOW_GENERIC_PURCHASE": True,
    },
    # --- Logging -------------------------------------------------------------
    "LOGGER_NAME": "vtpass",
    "LOG_REQUESTS": True,
    "STORE_RAW_RESPONSES": True,
    "BENEFICIARIES_ENABLED": True,
}

# Keys whose values are dicts merged one level deep with the defaults.
NESTED_KEYS = {"MESSAGING", "LIMITS", "REQUERY", "WEBHOOK", "NOTIFICATIONS", "API"}


class VTpassSettings:
    def __init__(self, user_settings=None, defaults=None):
        self._user_settings = user_settings
        self.defaults = defaults or DEFAULTS
        self._cache = None

    @property
    def user_settings(self):
        if self._user_settings is None:
            self._user_settings = getattr(django_settings, "VTPASS", {}) or {}
        return self._user_settings

    def _build(self):
        merged = copy.deepcopy(self.defaults)
        for key, value in self.user_settings.items():
            if key in NESTED_KEYS and isinstance(value, dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        return merged

    def as_dict(self):
        if self._cache is None:
            self._cache = self._build()
        return self._cache

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        data = self.as_dict()
        if name not in data:
            raise AttributeError(f"Unknown VTPASS setting: {name!r}")
        return data[name]

    def reload(self):
        self._user_settings = None
        self._cache = None

    # ---- derived values ------------------------------------------------------
    @property
    def base_url(self):
        url = self.as_dict()["BASE_URL"] or (SANDBOX_BASE_URL if self.SANDBOX else LIVE_BASE_URL)
        return url if url.endswith("/") else url + "/"

    @property
    def messaging_base_url(self):
        url = self.MESSAGING["BASE_URL"] or MESSAGING_BASE_URL
        return url if url.endswith("/") else url + "/"

    @property
    def timeout(self):
        return (self.CONNECT_TIMEOUT, self.READ_TIMEOUT)

    @property
    def logger(self):
        return logging.getLogger(self.LOGGER_NAME)

    def import_from_setting(self, key, value=None):
        path = value if value is not None else getattr(self, key)
        if not path:
            return None
        if not isinstance(path, str):
            return path
        try:
            return import_string(path)
        except ImportError as exc:
            raise VTpassConfigError(f"Could not import {path!r} from VTPASS[{key!r}]: {exc}") from exc

    def check(self):
        """Return a list of human readable configuration problems (used by the Django check)."""
        problems = []
        if self.AUTH_METHOD not in ("api_key", "basic"):
            problems.append("VTPASS['AUTH_METHOD'] must be 'api_key' or 'basic'.")
        elif self.AUTH_METHOD == "api_key":
            for key in ("API_KEY", "PUBLIC_KEY", "SECRET_KEY"):
                if not getattr(self, key):
                    problems.append(f"VTPASS['{key}'] is not set.")
        elif not (self.USERNAME and self.PASSWORD):
            problems.append("VTPASS['USERNAME'] and VTPASS['PASSWORD'] are required for basic auth.")
        if not self.SANDBOX and self.base_url.startswith(SANDBOX_BASE_URL):
            problems.append("VTPASS['SANDBOX'] is False but BASE_URL points at the sandbox.")
        if self.MESSAGING["DEFAULT_ROUTE"] not in (
            "normal", "dnd", "dnd-fallback", "simhost", "simhost-fallback"
        ):
            problems.append("VTPASS['MESSAGING']['DEFAULT_ROUTE'] is not a valid route.")
        return problems


vtpass_settings = VTpassSettings()


def _reload(*args, setting=None, **kwargs):
    if setting == "VTPASS":
        vtpass_settings.reload()


setting_changed.connect(_reload)
