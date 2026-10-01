"""Permission and throttle classes, configurable through ``VTPASS["API"]``."""

from django.utils.module_loading import import_string
from rest_framework.throttling import UserRateThrottle

from vtpass.settings import vtpass_settings


def _load(paths):
    return [import_string(p) if isinstance(p, str) else p for p in paths]


def default_permissions():
    return _load(vtpass_settings.API["PERMISSION_CLASSES"])


def admin_permissions():
    return _load(vtpass_settings.API["ADMIN_PERMISSION_CLASSES"])


class _SettingsRateThrottle(UserRateThrottle):
    setting = None

    def get_rate(self):
        return vtpass_settings.API.get(self.setting)


class PurchaseRateThrottle(_SettingsRateThrottle):
    """Limits purchases per user (``VTPASS["API"]["PURCHASE_THROTTLE_RATE"]``)."""

    scope = "vtpass_purchase"
    setting = "PURCHASE_THROTTLE_RATE"


class VerifyRateThrottle(_SettingsRateThrottle):
    """Limits customer lookups, which cost nothing to call and are easy to abuse."""

    scope = "vtpass_verify"
    setting = "VERIFY_THROTTLE_RATE"
