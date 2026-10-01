from rest_framework import serializers

from vtpass.api.serializers import MoneyField, PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VerifyAPIView, VTpassAPIView
from vtpass.constants import TV_SERVICE_IDS, ServiceID


class SmartcardSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=[s for s in TV_SERVICE_IDS if s != ServiceID.SHOWMAX])
    smartcard_number = serializers.CharField(max_length=32)


class TVPurchaseSerializer(PurchaseOptionsSerializer):
    provider = serializers.ChoiceField(choices=TV_SERVICE_IDS)
    action = serializers.ChoiceField(choices=("change", "renew"), default="change")
    smartcard_number = serializers.CharField(max_length=32, required=False, allow_blank=True)
    phone = PhoneField()
    variation_code = serializers.CharField(max_length=128, required=False, allow_blank=True)
    quantity = serializers.IntegerField(required=False, min_value=1, max_value=12)
    amount = MoneyField(required=False)

    def validate(self, attrs):
        if attrs["provider"] != ServiceID.SHOWMAX and not attrs.get("smartcard_number"):
            raise serializers.ValidationError({"smartcard_number": ["Required."]})
        if attrs["action"] == "change" and not attrs.get("variation_code"):
            raise serializers.ValidationError({"variation_code": ["Required to change bouquet."]})
        return attrs


class TVProvidersView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.tv.providers())


class TVBouquetsView(VTpassAPIView):
    def get(self, request, provider):
        return self.ok(self.vt.tv.bouquets(provider))


class TVVerifyView(VerifyAPIView):
    def post(self, request):
        data = self.validate(SmartcardSerializer)
        return self.ok(self.vt.tv.verify(data["provider"], data["smartcard_number"]), "Smartcard verified.")


class TVPurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(TVPurchaseSerializer)
        options = self.purchase_options(data)
        if data["action"] == "renew":
            # The renewal price is always verified server-side, never taken from the client.
            txn = self.vt.tv.renew(data["provider"], data["smartcard_number"], data["phone"], **options)
        else:
            txn = self.vt.tv.change(
                data["provider"], data.get("smartcard_number"), data["variation_code"], data["phone"],
                quantity=data.get("quantity"), amount=data.get("amount"), **options,
            )
        return self.purchase_response(txn)
