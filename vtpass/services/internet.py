"""Internet service providers: Smile and Spectranet."""

from vtpass.constants import ServiceID
from vtpass.services.airtime import ProductService
from vtpass.utils import normalize_phone


class InternetService(ProductService):
    def providers(self):
        return [
            {"service_id": ServiceID.SMILE, "name": "Smile"},
            {"service_id": ServiceID.SPECTRANET, "name": "Spectranet"},
        ]

    # ---- Smile -------------------------------------------------------------------
    def smile_plans(self):
        return self.engine.get_variations(ServiceID.SMILE)

    def verify_smile_email(self, email):
        """Find the Smile account(s) registered to an email address."""
        return self.client.verify_smile_email(email)

    def verify_smile_account(self, account_id):
        """Validate a Smile account ID / phone number."""
        return self.engine.verify(ServiceID.SMILE, account_id)

    def buy_smile(self, account_id, variation_code, phone, **options):
        return self.engine.purchase(
            service_id=ServiceID.SMILE, phone=phone, billers_code=account_id,
            variation_code=variation_code, **options,
        )

    # ---- Spectranet --------------------------------------------------------------
    def spectranet_plans(self):
        return self.engine.get_variations(ServiceID.SPECTRANET)

    def buy_spectranet(self, phone, variation_code, quantity=1, amount=None, **options):
        """Buy Spectranet PIN(s); the PIN/serial cards are in ``vend_details["cards"]``."""
        phone = normalize_phone(phone)
        return self.engine.purchase(
            service_id=ServiceID.SPECTRANET, phone=phone, billers_code=phone,
            variation_code=variation_code, quantity=quantity, amount=amount, **options,
        )
