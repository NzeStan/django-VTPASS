"""Education PINs: WAEC result checker, WAEC registration and JAMB (UTME / Direct Entry)."""

from vtpass.constants import ServiceID
from vtpass.exceptions import VTpassValidationError
from vtpass.services.airtime import ProductService


class EducationService(ProductService):
    def products(self):
        return [
            {"service_id": ServiceID.WAEC_RESULT_CHECKER, "name": "WAEC Result Checker PIN"},
            {"service_id": ServiceID.WAEC_REGISTRATION, "name": "WAEC Registration PIN"},
            {"service_id": ServiceID.JAMB, "name": "JAMB PIN (UTME / Direct Entry)"},
        ]

    def _default_variation(self, service_id, variation_code):
        if variation_code:
            return variation_code
        variations = self.engine.get_variations(service_id)
        if not variations:
            raise VTpassValidationError(f"No plans available for {service_id}.")
        return variations[0]["variation_code"]

    def waec_result_checker(self, phone, quantity=1, variation_code=None, **options):
        """Buy WAEC result checker PIN(s). Serial/PIN pairs are in ``vend_details["cards"]``."""
        return self.engine.purchase(
            service_id=ServiceID.WAEC_RESULT_CHECKER,
            phone=phone,
            variation_code=self._default_variation(ServiceID.WAEC_RESULT_CHECKER, variation_code),
            quantity=quantity,
            **options,
        )

    def waec_registration(self, phone, quantity=1, variation_code=None, **options):
        """Buy WAEC registration PIN(s). PINs are in ``vend_details["tokens"]``."""
        return self.engine.purchase(
            service_id=ServiceID.WAEC_REGISTRATION,
            phone=phone,
            variation_code=self._default_variation(ServiceID.WAEC_REGISTRATION, variation_code),
            quantity=quantity,
            **options,
        )

    def verify_jamb_profile(self, profile_id, variation_code):
        """Validate a JAMB profile ID for the chosen exam type (``utme``/``de`` variation code)."""
        return self.engine.verify(ServiceID.JAMB, profile_id, type=variation_code)

    def jamb(self, profile_id, variation_code, phone, **options):
        """Buy a JAMB PIN; the PIN text is in ``transaction.purchased_code``."""
        return self.engine.purchase(
            service_id=ServiceID.JAMB,
            phone=phone,
            billers_code=profile_id,
            variation_code=variation_code,
            **options,
        )
