from rest_framework import serializers

from vtpass.api.serializers import MoneyField, PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VerifyAPIView, VTpassAPIView
from vtpass.constants import ServiceID


class SmileVerifySerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    account_id = serializers.CharField(max_length=32, required=False)

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("account_id"):
            raise serializers.ValidationError("Provide an email or an account_id.")
        return attrs


class InternetPurchaseSerializer(PurchaseOptionsSerializer):
    provider = serializers.ChoiceField(choices=(ServiceID.SMILE, ServiceID.SPECTRANET))
    phone = PhoneField()
    variation_code = serializers.CharField(max_length=128)
    account_id = serializers.CharField(max_length=32, required=False, allow_blank=True)
    quantity = serializers.IntegerField(required=False, min_value=1, max_value=10, default=1)
    amount = MoneyField(required=False)

    def validate(self, attrs):
        if attrs["provider"] == ServiceID.SMILE and not attrs.get("account_id"):
            raise serializers.ValidationError({"account_id": ["Required for Smile."]})
        return attrs


class InternetProvidersView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.internet.providers())


class SmileVerifyView(VerifyAPIView):
    def post(self, request):
        data = self.validate(SmileVerifySerializer)
        if data.get("email"):
            result = self.vt.internet.verify_smile_email(data["email"])
        else:
            result = self.vt.internet.verify_smile_account(data["account_id"])
        return self.ok(result, "Account verified.")


class InternetPurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(InternetPurchaseSerializer)
        options = self.purchase_options(data)
        if data["provider"] == ServiceID.SMILE:
            txn = self.vt.internet.buy_smile(data["account_id"], data["variation_code"], data["phone"], **options)
        else:
            txn = self.vt.internet.buy_spectranet(
                data["phone"], data["variation_code"], quantity=data["quantity"], amount=data.get("amount"),
                **options,
            )
        return self.purchase_response(txn)
