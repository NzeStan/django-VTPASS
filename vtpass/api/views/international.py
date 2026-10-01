from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from vtpass.api.serializers import MoneyField, PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VTpassAPIView


def _require(request, *names):
    values = {name: request.query_params.get(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValidationError({name: ["This query parameter is required."] for name in missing})
    return values


class InternationalPurchaseSerializer(PurchaseOptionsSerializer):
    recipient = serializers.CharField(max_length=20, help_text="Foreign number including country code.")
    country_code = serializers.CharField(max_length=3)
    operator_id = serializers.CharField(max_length=16)
    product_type_id = serializers.CharField(max_length=16)
    variation_code = serializers.CharField(max_length=128)
    phone = PhoneField()
    email = serializers.EmailField()
    amount = MoneyField(required=False)


class CountriesView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.international.countries())


class ProductTypesView(VTpassAPIView):
    def get(self, request):
        params = _require(request, "country")
        return self.ok(self.vt.international.product_types(params["country"]))


class OperatorsView(VTpassAPIView):
    def get(self, request):
        params = _require(request, "country", "product_type_id")
        return self.ok(self.vt.international.operators(params["country"], params["product_type_id"]))


class InternationalVariationsView(VTpassAPIView):
    def get(self, request):
        params = _require(request, "operator_id", "product_type_id")
        return self.ok(self.vt.international.variations(params["operator_id"], params["product_type_id"]))


class InternationalPurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(InternationalPurchaseSerializer)
        options = self.purchase_options(data)
        options.pop("email", None)
        txn = self.vt.international.buy(
            recipient=data["recipient"], country_code=data["country_code"], operator_id=data["operator_id"],
            product_type_id=data["product_type_id"], variation_code=data["variation_code"],
            email=data["email"], phone=data["phone"], amount=data.get("amount"), **options,
        )
        return self.purchase_response(txn)
