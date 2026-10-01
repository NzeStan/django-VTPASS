"""Catalogue, customer verification, network detection, quotes, generic purchase and merchant tools."""

from decimal import Decimal

from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError

from vtpass.api.permissions import admin_permissions
from vtpass.api.serializers import PhoneField, PurchaseOptionsSerializer, QuoteRequestSerializer, VerifySerializer
from vtpass.api.views.base import PurchaseAPIView, VerifyAPIView, VTpassAPIView
from vtpass.constants import SMSRoute
from vtpass.settings import vtpass_settings
from vtpass.utils import detect_network, normalize_phone


class CategoryListView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.catalog.categories())


class ServiceListView(VTpassAPIView):
    def get(self, request):
        category = request.query_params.get("category")
        if not category:
            raise ValidationError({"category": ["This query parameter is required."]})
        return self.ok(self.vt.catalog.services(category))


class VariationListView(VTpassAPIView):
    def get(self, request, service_id):
        params = {k: v for k, v in request.query_params.items() if k in ("operator_id", "product_type_id")}
        return self.ok(self.vt.catalog.variations(service_id, **params))


class OptionListView(VTpassAPIView):
    def get(self, request, service_id):
        name = request.query_params.get("name")
        if not name:
            raise ValidationError({"name": ["This query parameter is required."]})
        return self.ok(self.vt.catalog.options(service_id, name))


class DetectNetworkView(VTpassAPIView):
    def get(self, request):
        phone = normalize_phone(request.query_params.get("phone", ""))
        network = detect_network(phone)
        return self.ok({"phone": phone, "network": network.value if network else None})


class VerifyView(VerifyAPIView):
    """Generic customer lookup for any service (meter, smartcard, profile ID, account ID...)."""

    def post(self, request):
        data = self.validate(VerifySerializer)
        result = self.vt.verify(data["service_id"], data["billers_code"], type=data.get("type") or None)
        return self.ok(result, "Customer verified.")


class GenericPurchaseSerializer(PurchaseOptionsSerializer):
    service_id = serializers.CharField(max_length=64)
    phone = PhoneField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, min_value=Decimal("1"))
    billers_code = serializers.CharField(max_length=128, required=False, allow_blank=True)
    variation_code = serializers.CharField(max_length=128, required=False, allow_blank=True)
    quantity = serializers.IntegerField(required=False, min_value=1, max_value=100)
    subscription_type = serializers.ChoiceField(choices=("change", "renew"), required=False)
    extra = serializers.DictField(child=serializers.CharField(max_length=255), required=False, default=dict)


class GenericPurchaseView(PurchaseAPIView):
    """Buy any VTpass product by service ID (also covers products VTpass adds in future)."""

    def post(self, request):
        if not vtpass_settings.API.get("ALLOW_GENERIC_PURCHASE", True):
            raise NotFound()
        data = self.validate(GenericPurchaseSerializer)
        extra = data.get("extra", {})
        txn = self.vt.purchase(
            service_id=data["service_id"],
            phone=data["phone"],
            amount=data.get("amount"),
            billers_code=data.get("billers_code") or None,
            variation_code=data.get("variation_code") or None,
            quantity=data.get("quantity"),
            subscription_type=data.get("subscription_type"),
            extra=extra,
            **self.purchase_options(data),
        )
        return self.purchase_response(txn)


class QuoteView(VTpassAPIView):
    """What will the customer pay (fee/discount) and earn (cashback) for this purchase?"""

    def post(self, request):
        data = self.validate(QuoteRequestSerializer)
        params = {k: data[k] for k in ("operator_id", "product_type_id") if data.get(k)}
        quote = self.vt.quote(
            data["service_id"], amount=data.get("amount"), variation_code=data.get("variation_code") or None,
            quantity=data.get("quantity") or 1, user=request.user, variation_params=params,
        )
        return self.ok(quote.as_dict())


# ---- merchant (admin only) ------------------------------------------------------------
class MerchantBalanceView(VTpassAPIView):
    def get_permissions(self):
        return [p() for p in admin_permissions()]

    def get(self, request):
        return self.ok({"balance": str(self.vt.balance()), "currency": vtpass_settings.CURRENCY})


class SMSSendSerializer(serializers.Serializer):
    recipients = serializers.ListField(child=serializers.CharField(max_length=20), min_length=1, max_length=10000)
    message = serializers.CharField(max_length=918)
    sender = serializers.CharField(max_length=11, required=False, allow_blank=True)
    route = serializers.ChoiceField(choices=SMSRoute.choices, required=False)
    client_batch_id = serializers.CharField(max_length=64, required=False, allow_blank=True)


class SMSSendView(VTpassAPIView):
    def get_permissions(self):
        return [p() for p in admin_permissions()]

    def post(self, request):
        data = self.validate(SMSSendSerializer)
        result = self.vt.sms.send(
            data["recipients"], data["message"], sender=data.get("sender") or None, route=data.get("route"),
            user=request.user, purpose="api", client_batch_id=data.get("client_batch_id") or None,
        )
        return self.ok(
            {"batch_id": result.batch_id, "response_code": result.response_code, "messages": result.messages},
            "Message processed.",
        )


class SMSBalanceView(VTpassAPIView):
    def get_permissions(self):
        return [p() for p in admin_permissions()]

    def get(self, request):
        return self.ok({"units": str(self.vt.sms.balance())})
