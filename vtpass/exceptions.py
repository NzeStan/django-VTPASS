"""
Exceptions for the VTpass package.
This module defines custom exceptions for different error cases.
"""

from django.utils.translation import gettext_lazy as _


class VTpassError(Exception):
    """Base exception for all VTpass errors."""
    def __init__(self, message=None, *args, **kwargs):
        self.message = message or _("An error occurred with the VTpass integration")
        super().__init__(self.message, *args, **kwargs)


class VTpassConfigError(VTpassError):
    """Raised when there's an issue with the VTpass configuration."""
    def __init__(self, message=None, *args, **kwargs):
        self.message = message or _("VTpass configuration error")
        super().__init__(self.message, *args, **kwargs)


class VTpassAPIError(VTpassError):
    """Raised when there's an error from the VTpass API."""
    def __init__(self, message=None, status_code=None, response=None, *args, **kwargs):
        self.message = message or _("VTpass API error")
        self.status_code = status_code
        self.response = response
        super().__init__(self.message, *args, **kwargs)


class VTpassNetworkError(VTpassError):
    """Raised when there's a network error when calling the VTpass API."""
    def __init__(self, message=None, original_error=None, *args, **kwargs):
        self.message = message or _("Network error while connecting to VTpass API")
        self.original_error = original_error
        super().__init__(self.message, *args, **kwargs)


class VTpassAuthenticationError(VTpassAPIError):
    """Raised when there's an authentication error with the VTpass API."""
    def __init__(self, message=None, *args, **kwargs):
        self.message = message or _("VTpass API authentication error")
        super().__init__(self.message, *args, **kwargs)


class VTpassValidationError(VTpassError):
    """Raised when there's a validation error with the data provided."""
    def __init__(self, message=None, field=None, errors=None, *args, **kwargs):
        self.message = message or _("Validation error")
        self.field = field
        self.errors = errors or {}
        super().__init__(self.message, *args, **kwargs)


class VTpassTransactionError(VTpassError):
    """Raised when there's an error with a transaction."""
    def __init__(self, message=None, transaction_id=None, *args, **kwargs):
        self.message = message or _("Transaction error")
        self.transaction_id = transaction_id
        super().__init__(self.message, *args, **kwargs)


class VTpassServiceError(VTpassError):
    """Raised when there's an error with a specific service."""
    def __init__(self, message=None, service=None, *args, **kwargs):
        self.message = message or _("Service error")
        self.service = service
        super().__init__(self.message, *args, **kwargs)


class VTpassWebhookError(VTpassError):
    """Raised when there's an error processing a webhook."""
    def __init__(self, message=None, payload=None, *args, **kwargs):
        self.message = message or _("Webhook processing error")
        self.payload = payload
        super().__init__(self.message, *args, **kwargs)