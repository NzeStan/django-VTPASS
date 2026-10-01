"""TV subscriptions: DSTV, GOtv, Startimes and Showmax."""

from vtpass.constants import ServiceID, SubscriptionType, TV_SERVICE_IDS
from vtpass.exceptions import VTpassValidationError
from vtpass.services.airtime import ProductService
from vtpass.utils import normalize_phone, to_decimal

TV_NAMES = {
    ServiceID.DSTV: "DStv",
    ServiceID.GOTV: "GOtv",
    ServiceID.STARTIMES: "StarTimes",
    ServiceID.SHOWMAX: "Showmax",
}


class TVService(ProductService):
    def providers(self):
        return [{"service_id": sid, "name": TV_NAMES[sid]} for sid in TV_SERVICE_IDS]

    @staticmethod
    def _service_id(provider):
        service_id = str(provider).lower()
        if service_id not in TV_SERVICE_IDS:
            raise VTpassValidationError(f"Unknown TV provider {provider!r}.", errors={"provider": ["Invalid."]})
        return service_id

    def bouquets(self, provider):
        return self.engine.get_variations(self._service_id(provider))

    def verify(self, provider, smartcard_number):
        """
        Validate a smartcard/IUC. The result includes ``Customer_Name``,
        ``Status``, ``Due_Date``, ``Current_Bouquet`` and ``Renewal_Amount``
        (DStv/GOtv), which is what :meth:`renew` charges.
        """
        service_id = self._service_id(provider)
        if service_id == ServiceID.SHOWMAX:
            raise VTpassValidationError("Showmax uses phone numbers and needs no verification.")
        return self.engine.verify(service_id, smartcard_number)

    def change(self, provider, smartcard_number, variation_code, phone, quantity=None, amount=None, **options):
        """
        Buy a (new or different) bouquet. For DStv/GOtv this is
        ``subscription_type=change``; ``quantity`` buys several months.
        """
        service_id = self._service_id(provider)
        if service_id == ServiceID.SHOWMAX:
            return self.showmax(phone, variation_code, **options)
        subscription_type = SubscriptionType.CHANGE if service_id in (ServiceID.DSTV, ServiceID.GOTV) else None
        return self.engine.purchase(
            service_id=service_id,
            phone=phone,
            billers_code=smartcard_number,
            variation_code=variation_code,
            amount=amount,
            quantity=quantity,
            subscription_type=subscription_type,
            **options,
        )

    def renew(self, provider, smartcard_number, phone, amount=None, **options):
        """
        Renew the current DStv/GOtv bouquet. When ``amount`` is omitted the
        smartcard is verified first and ``Renewal_Amount`` (which includes any
        promo pricing) is used.
        """
        service_id = self._service_id(provider)
        if service_id not in (ServiceID.DSTV, ServiceID.GOTV):
            raise VTpassValidationError("Renewal is only available for DStv and GOtv; use change().")
        if amount is None:
            details = self.verify(service_id, smartcard_number)
            amount = to_decimal(details.get("Renewal_Amount"))
            if not amount:
                raise VTpassValidationError("Could not determine the renewal amount; pass amount explicitly.")
        return self.engine.purchase(
            service_id=service_id,
            phone=phone,
            billers_code=smartcard_number,
            amount=amount,
            subscription_type=SubscriptionType.RENEW,
            **options,
        )

    def showmax(self, phone, variation_code, **options):
        """Buy a Showmax plan. The voucher code is in ``transaction.vend_details``."""
        phone = normalize_phone(phone)
        return self.engine.purchase(
            service_id=ServiceID.SHOWMAX, phone=phone, billers_code=phone, variation_code=variation_code, **options
        )
