"""Insurance: third-party motor (``ui-insure``) and personal accident (``personal-accident-insurance``)."""

from django.core.cache import cache

from vtpass.constants import InsuranceOption, ServiceID
from vtpass.exceptions import VTpassValidationError
from vtpass.services.airtime import ProductService
from vtpass.settings import vtpass_settings


class InsuranceService(ProductService):
    def plans(self, service_id=ServiceID.THIRD_PARTY_MOTOR):
        """Motor: Private (1), Commercial (2), Tricycle (3), Motorcycle (4). Pass
        ``ServiceID.PERSONAL_ACCIDENT`` for personal accident plans."""
        return self.engine.get_variations(service_id)

    def personal_accident_plans(self):
        return self.engine.get_variations(ServiceID.PERSONAL_ACCIDENT)

    def personal_accident(
        self,
        *,
        variation_code,
        phone,
        full_name,
        address,
        dob,
        next_kin_name,
        next_kin_phone,
        business_occupation,
        **options,
    ):
        """
        Buy personal accident cover. ``dob`` is ``YYYY-MM-DD`` (a ``date`` is
        accepted too). VTpass uses the insured's full name as the billers code.
        """
        if hasattr(dob, "isoformat"):
            dob = dob.isoformat()
        extra = {
            "full_name": full_name,
            "address": address,
            "dob": dob,
            "next_kin_name": next_kin_name,
            "next_kin_phone": next_kin_phone,
            "business_occupation": business_occupation,
        }
        missing = [k for k, v in extra.items() if v in (None, "")]
        if missing:
            raise VTpassValidationError("Missing insurance details.", errors={k: ["Required."] for k in missing})
        options_extra = options.pop("extra", None) or {}
        return self.engine.purchase(
            service_id=ServiceID.PERSONAL_ACCIDENT,
            phone=phone,
            billers_code=full_name,
            variation_code=variation_code,
            extra={**extra, **options_extra},
            **options,
        )

    def options(self, option, parent=None):
        """
        Lookup lists needed for the purchase form: ``color``,
        ``engine-capacity``, ``state``, ``lga`` (parent = state code),
        ``brand`` and ``model`` (parent = brand code). Cached.
        """
        if option not in InsuranceOption.ALL:
            raise VTpassValidationError(f"Unknown insurance option {option!r}.")
        if option in InsuranceOption.REQUIRES_PARENT and parent in (None, ""):
            raise VTpassValidationError(f"The {option!r} option needs a parent code.")
        key = f"vtpass:insurance:{option}:{parent or ''}"
        value = cache.get(key)
        if value is None:
            value = self.client.get_insurance_options(option, parent)
            cache.set(key, value, vtpass_settings.CATALOG_CACHE_TIMEOUT)
        return value

    def third_party_motor(
        self,
        *,
        plate_number,
        variation_code,
        phone,
        insured_name,
        engine_capacity,
        chasis_number,
        vehicle_make,
        vehicle_color,
        vehicle_model,
        year_of_make,
        state,
        lga,
        email,
        **options,
    ):
        """Buy a third-party motor policy. The certificate link is in ``vend_details["certUrl"]``."""
        extra = {
            "Insured_Name": insured_name,
            "engine_capacity": engine_capacity,
            "Chasis_Number": chasis_number,
            "Plate_Number": plate_number,
            "vehicle_make": vehicle_make,
            "vehicle_color": vehicle_color,
            "vehicle_model": vehicle_model,
            "YearofMake": year_of_make,
            "state": state,
            "lga": lga,
        }
        missing = [k for k, v in extra.items() if v in (None, "")]
        if missing:
            raise VTpassValidationError(
                "Missing insurance details.", errors={k: ["Required."] for k in missing}
            )
        options_extra = options.pop("extra", None) or {}
        return self.engine.purchase(
            service_id=ServiceID.THIRD_PARTY_MOTOR,
            phone=phone,
            billers_code=plate_number,
            variation_code=variation_code,
            email=email,
            extra={**extra, **options_extra},
            **options,
        )
