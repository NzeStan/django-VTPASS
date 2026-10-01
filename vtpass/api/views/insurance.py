from rest_framework import serializers

from vtpass.api.serializers import PhoneField, PurchaseOptionsSerializer
from vtpass.api.views.base import PurchaseAPIView, VTpassAPIView
from vtpass.constants import InsuranceOption, ServiceID


class MotorInsuranceSerializer(PurchaseOptionsSerializer):
    plate_number = serializers.CharField(max_length=20)
    variation_code = serializers.CharField(max_length=16)
    phone = PhoneField()
    email = serializers.EmailField()
    insured_name = serializers.CharField(max_length=128)
    engine_capacity = serializers.CharField(max_length=32)
    chasis_number = serializers.CharField(max_length=64)
    vehicle_make = serializers.CharField(max_length=32)
    vehicle_color = serializers.CharField(max_length=32)
    vehicle_model = serializers.CharField(max_length=32)
    year_of_make = serializers.CharField(max_length=4)
    state = serializers.CharField(max_length=32)
    lga = serializers.CharField(max_length=32)


class PersonalAccidentSerializer(PurchaseOptionsSerializer):
    variation_code = serializers.CharField(max_length=64)
    phone = PhoneField()
    full_name = serializers.CharField(max_length=128)
    address = serializers.CharField(max_length=255)
    dob = serializers.DateField(input_formats=["%Y-%m-%d"])
    next_kin_name = serializers.CharField(max_length=128)
    next_kin_phone = PhoneField()
    business_occupation = serializers.CharField(max_length=128)


class InsurancePlansView(VTpassAPIView):
    """``?product=personal-accident-insurance`` for personal accident plans (default: motor)."""

    def get(self, request):
        product = request.query_params.get("product") or ServiceID.THIRD_PARTY_MOTOR
        if product not in (ServiceID.THIRD_PARTY_MOTOR, ServiceID.PERSONAL_ACCIDENT):
            return self.fail("Unknown insurance product.", status=404)
        return self.ok(self.vt.insurance.plans(product))


class InsuranceOptionsView(VTpassAPIView):
    """``/insurance/options/<color|engine-capacity|state|lga|brand|model>/?parent=<code>``"""

    def get(self, request, option):
        if option not in InsuranceOption.ALL:
            return self.fail("Unknown option.", status=404)
        return self.ok(self.vt.insurance.options(option, parent=request.query_params.get("parent")))


class MotorInsurancePurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(MotorInsuranceSerializer)
        options = self.purchase_options(data)
        options.pop("email", None)
        txn = self.vt.insurance.third_party_motor(
            plate_number=data["plate_number"], variation_code=data["variation_code"], phone=data["phone"],
            insured_name=data["insured_name"], engine_capacity=data["engine_capacity"],
            chasis_number=data["chasis_number"], vehicle_make=data["vehicle_make"],
            vehicle_color=data["vehicle_color"], vehicle_model=data["vehicle_model"],
            year_of_make=data["year_of_make"], state=data["state"], lga=data["lga"], email=data["email"],
            **options,
        )
        return self.purchase_response(txn)


class PersonalAccidentPurchaseView(PurchaseAPIView):
    def post(self, request):
        data = self.validate(PersonalAccidentSerializer)
        txn = self.vt.insurance.personal_accident(
            variation_code=data["variation_code"], phone=data["phone"], full_name=data["full_name"],
            address=data["address"], dob=data["dob"], next_kin_name=data["next_kin_name"],
            next_kin_phone=data["next_kin_phone"], business_occupation=data["business_occupation"],
            **self.purchase_options(data),
        )
        return self.purchase_response(txn)
