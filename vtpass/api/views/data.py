from rest_framework import serializers

from vtpass.api.serializers import PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VTpassAPIView
from vtpass.constants import Network


class DataPurchaseSerializer(PurchaseOptionsSerializer):
    phone = PhoneField()
    variation_code = serializers.CharField(max_length=128)
    network = serializers.ChoiceField(choices=Network.choices, required=False)
    sme = serializers.BooleanField(required=False, default=False)


class DataNetworksView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.data.networks())


class DataPlansView(VTpassAPIView):
    def get(self, request):
        network = request.query_params.get("network")
        phone = request.query_params.get("phone")
        sme = request.query_params.get("sme") in ("1", "true", "yes")
        return self.ok(self.vt.data.plans(network=network, phone=phone, sme=sme))


class DataPurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(DataPurchaseSerializer)
        txn = self.vt.data.buy(
            data["phone"], data["variation_code"], network=data.get("network"), sme=data.get("sme", False),
            **self.purchase_options(data),
        )
        return self.purchase_response(txn)
