from decimal import Decimal

from rest_framework import serializers

from vtpass.api.serializers import MoneyField, PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VTpassAPIView
from vtpass.constants import Network


class AirtimePurchaseSerializer(PurchaseOptionsSerializer):
    phone = PhoneField()
    amount = MoneyField(min_value=Decimal("50"))
    network = serializers.ChoiceField(choices=Network.choices, required=False,
                                      help_text="Detected from the number when omitted.")


class AirtimeNetworksView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.airtime.networks())


class AirtimePurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(AirtimePurchaseSerializer)
        txn = self.vt.airtime.buy(
            data["phone"], data["amount"], network=data.get("network"), **self.purchase_options(data)
        )
        return self.purchase_response(txn)
