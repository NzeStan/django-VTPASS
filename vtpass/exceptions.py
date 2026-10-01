"""
Exception hierarchy for django-vtpass.

Everything raised by the package derives from :class:`VTpassError`, so callers
can catch a single type. The subclasses tell you *who* has to act:

* ``VTpassValidationError`` – bad input from the end user (show it to them).
* ``VTpassAPIError`` – VTpass rejected the request (``code`` holds the VTpass code).
* ``VTpassMerchantError`` – your VTpass account/config needs attention
  (low balance, IP not whitelisted, bad credentials...). Never blame the user.
* ``VTpassNetworkError`` – VTpass could not be reached or did not answer.
* ``InsufficientFunds`` / ``PurchaseDenied`` / ``LimitExceeded`` – raised by
  the purchase pipeline before any money leaves your VTpass wallet.
"""


class VTpassError(Exception):
    default_message = "An error occurred with the VTpass integration."

    def __init__(self, message=None, **context):
        self.message = str(message or self.default_message)
        self.context = context
        super().__init__(self.message)

    def __str__(self):
        return self.message


class VTpassConfigError(VTpassError):
    default_message = "VTpass is not configured correctly."


class VTpassValidationError(VTpassError):
    default_message = "Invalid data."

    def __init__(self, message=None, errors=None, **context):
        self.errors = errors or {}
        super().__init__(message, **context)


class VTpassAPIError(VTpassError):
    default_message = "VTpass returned an error."

    def __init__(self, message=None, code=None, status_code=None, response=None, **context):
        self.code = code
        self.status_code = status_code
        self.response = response
        super().__init__(message, **context)


class VTpassMerchantError(VTpassAPIError):
    default_message = "The VTpass merchant account cannot process this request."


class VTpassAuthenticationError(VTpassMerchantError):
    default_message = "VTpass rejected the API credentials."


class VTpassNetworkError(VTpassError):
    default_message = "Could not reach VTpass."

    def __init__(self, message=None, original_error=None, timeout=False, **context):
        self.original_error = original_error
        self.timeout = timeout
        super().__init__(message, **context)


class VTpassTransactionError(VTpassError):
    default_message = "Transaction error."

    def __init__(self, message=None, transaction=None, **context):
        self.transaction = transaction
        super().__init__(message, **context)


class InsufficientFunds(VTpassTransactionError):
    default_message = "Insufficient wallet balance."


class PurchaseDenied(VTpassTransactionError):
    """Raise from a ``pre_purchase`` receiver to block a purchase (PIN checks, KYC, fraud rules...)."""

    default_message = "Purchase not allowed."


class LimitExceeded(PurchaseDenied):
    default_message = "Transaction limit exceeded."


class DuplicateTransaction(VTpassTransactionError):
    default_message = "A transaction with this idempotency key already exists."


class VTpassWebhookError(VTpassError):
    default_message = "Invalid webhook request."


class SMSError(VTpassAPIError):
    default_message = "The SMS could not be sent."
