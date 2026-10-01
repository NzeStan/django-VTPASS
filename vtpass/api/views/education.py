from rest_framework import serializers

from vtpass.api.serializers import PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VerifyAPIView, VTpassAPIView
from vtpass.constants import ServiceID

PRODUCTS = (ServiceID.WAEC_RESULT_CHECKER, ServiceID.WAEC_REGISTRATION, ServiceID.JAMB)


class JambVerifySerializer(serializers.Serializer):
    profile_id = serializers.CharField(max_length=32)
    variation_code = serializers.CharField(max_length=64)


class EducationPurchaseSerializer(PurchaseOptionsSerializer):
    product = serializers.ChoiceField(choices=PRODUCTS)
    phone = PhoneField()
    quantity = serializers.IntegerField(required=False, min_value=1, max_value=10, default=1)
    variation_code = serializers.CharField(max_length=64, required=False, allow_blank=True)
    profile_id = serializers.CharField(max_length=32, required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["product"] == ServiceID.JAMB:
            errors = {}
            if not attrs.get("profile_id"):
                errors["profile_id"] = ["Required for JAMB."]
            if not attrs.get("variation_code"):
                errors["variation_code"] = ["Required for JAMB."]
            if errors:
                raise serializers.ValidationError(errors)
        return attrs


class EducationProductsView(VTpassAPIView):
    def get(self, request):
        return self.ok(self.vt.education.products())


class JambVerifyView(VerifyAPIView):
    def post(self, request):
        data = self.validate(JambVerifySerializer)
        result = self.vt.education.verify_jamb_profile(data["profile_id"], data["variation_code"])
        return self.ok(result, "Profile verified.")


class EducationPurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(EducationPurchaseSerializer)
        options = self.purchase_options(data)
        product = data["product"]
        if product == ServiceID.JAMB:
            txn = self.vt.education.jamb(data["profile_id"], data["variation_code"], data["phone"], **options)
        elif product == ServiceID.WAEC_REGISTRATION:
            txn = self.vt.education.waec_registration(
                data["phone"], quantity=data["quantity"], variation_code=data.get("variation_code") or None, **options
            )
        else:
            txn = self.vt.education.waec_result_checker(
                data["phone"], quantity=data["quantity"], variation_code=data.get("variation_code") or None, **options
            )
        return self.purchase_response(txn)
