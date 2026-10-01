"""Logging helpers. Secrets and vended codes (tokens, PINs) are always masked."""

import logging

from vtpass.utils import mask_data

logger = logging.getLogger("vtpass")


def get_logger():
    from vtpass.settings import vtpass_settings

    return vtpass_settings.logger


def log_request(method, url, payload=None):
    from vtpass.settings import vtpass_settings

    if vtpass_settings.LOG_REQUESTS:
        get_logger().info("VTpass request %s %s %s", method, url, mask_data(payload or {}))


def log_response(method, url, status_code, payload, elapsed=None):
    from vtpass.settings import vtpass_settings

    if vtpass_settings.LOG_REQUESTS:
        get_logger().info(
            "VTpass response %s %s status=%s elapsed=%.3fs %s",
            method, url, status_code, elapsed or 0.0, mask_data(payload),
        )
