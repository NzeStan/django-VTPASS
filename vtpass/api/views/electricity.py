from rest_framework import serializers

from vtpass.api.serializers import MoneyField, PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VerifyAPIView, VTpassAPIView
from vtpass.constants import MeterType


class MeterSerializer(serializers.Serializer):
    disco = serializers.CharField(max_length=64, help_text="Service ID (ikeja-electric) or short name (ikedc).")
    meter_number = serializers.CharField(max_length=32)
    meter_type = serializers.ChoiceField(choices=MeterType.choices)


class ElectricityPurchaseSerializer(MeterSerializer, PurchaseOptionsSerializer):
    amount = MoneyField()
    phone = PhoneField()


class DiscoListView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.electricity.discos())


class MeterVerifyView(VerifyAPIView):
    def post(self, request):
        data = self.validate(MeterSerializer)
        result = self.vt.electricity.verify(data["disco"], data["meter_number"], data["meter_type"])
        return self.ok(result, "Meter verified.")


class ElectricityPurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(ElectricityPurchaseSerializer)
        txn = self.vt.electricity.buy(
            data["disco"], data["meter_number"], data["meter_type"], data["amount"], data["phone"],
            **self.purchase_options(data),
        )
        return self.purchase_response(txn)
