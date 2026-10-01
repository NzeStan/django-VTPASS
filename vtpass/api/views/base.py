"""
Base view: response envelope, error mapping and purchase plumbing.

Every response looks like ``{"success": bool, "message": str, "data": ...}``.
Purchases return 201 (successful), 202 (pending) or 422 (failed) with the
transaction in ``data``. Send an ``Idempotency-Key`` header on purchases so a
retried request (flaky mobile network) can never buy twice.
"""

import logging

from rest_framework import status as http
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from vtpass.api.permissions import PurchaseRateThrottle, VerifyRateThrottle, default_permissions
from vtpass.api.serializers import TransactionSerializer, public_message
from vtpass.constants import Status
from vtpass.exceptions import (
    DuplicateTransaction,
    InsufficientFunds,
    PurchaseDenied,
    VTpassAPIError,
    VTpassConfigError,
    VTpassError,
    VTpassMerchantError,
    VTpassNetworkError,
    VTpassValidationError,
)
from vtpass.services import VTpass

logger = logging.getLogger("vtpass")

UNAVAILABLE = "This service is temporarily unavailable. Please try again shortly."


class VTpassPagination(PageNumberPagination):
    """``?page=2&page_size=50``. List payloads look like ``{count, next, previous, results}``."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class VTpassAPIView(APIView):
    vtpass_class = VTpass

    def get_permissions(self):
        if self.permission_classes is not APIView.permission_classes:
            return super().get_permissions()
        return [permission() for permission in default_permissions()]

    @property
    def vt(self):
        if not hasattr(self, "_vt"):
            self._vt = self.vtpass_class()
        return self._vt

    # ---- responses ----------------------------------------------------------------
    @staticmethod
    def ok(data=None, message="OK", status=http.HTTP_200_OK):
        return Response({"success": True, "message": message, "data": data}, status=status)

    @staticmethod
    def fail(message, status=http.HTTP_400_BAD_REQUEST, errors=None, data=None):
        body = {"success": False, "message": str(message)}
        if errors:
            body["errors"] = errors
        if data is not None:
            body["data"] = data
        return Response(body, status=status)

    def validate(self, serializer_class, data=None):
        serializer = serializer_class(data=self.request.data if data is None else data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def handle_exception(self, exc):
        if isinstance(exc, VTpassValidationError):
            return self.fail(exc.message, errors=exc.errors or None)
        if isinstance(exc, InsufficientFunds):
            return self.fail(exc.message, status=http.HTTP_402_PAYMENT_REQUIRED)
        if isinstance(exc, DuplicateTransaction):
            return self.fail(exc.message, status=http.HTTP_409_CONFLICT)
        if isinstance(exc, PurchaseDenied):
            return self.fail(exc.message, status=http.HTTP_403_FORBIDDEN)
        if isinstance(exc, (VTpassMerchantError, VTpassConfigError)):
            logger.error("VTpass merchant/config problem: %s", exc)
            return self.fail(UNAVAILABLE, status=http.HTTP_503_SERVICE_UNAVAILABLE)
        if isinstance(exc, VTpassNetworkError):
            return self.fail(UNAVAILABLE, status=http.HTTP_503_SERVICE_UNAVAILABLE)
        if isinstance(exc, VTpassAPIError):
            return self.fail(exc.message or UNAVAILABLE, status=http.HTTP_502_BAD_GATEWAY)
        if isinstance(exc, VTpassError):
            return self.fail(exc.message)
        return super().handle_exception(exc)

    # ---- purchases ----------------------------------------------------------------
    def purchase_options(self, data):
        """Common keyword arguments for every service ``buy`` call."""
        key = self.request.headers.get("Idempotency-Key") or self.request.headers.get("X-Idempotency-Key")
        return {
            "user": self.request.user,
            "email": data.get("email") or getattr(self.request.user, "email", "") or None,
            "idempotency_key": (key or "")[:128] or None,
            "metadata": data.get("metadata") or {},
            "channel": "api",
            "request": self.request,
            "save_beneficiary": data.get("save_beneficiary", False),
        }

    def purchase_response(self, txn):
        data = TransactionSerializer(txn).data
        message = public_message(txn)
        if txn.status == Status.SUCCESSFUL:
            return self.ok(data, message, status=http.HTTP_201_CREATED)
        if txn.status in Status.open():
            return self.ok(data, message, status=http.HTTP_202_ACCEPTED)
        return self.fail(message, status=http.HTTP_422_UNPROCESSABLE_ENTITY, data=data)


class PurchaseAPIView(VTpassAPIView):
    throttle_classes = [PurchaseRateThrottle]


class VerifyAPIView(VTpassAPIView):
    throttle_classes = [VerifyRateThrottle]
