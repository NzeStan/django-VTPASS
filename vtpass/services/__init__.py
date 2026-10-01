"""
High-level API. One object gives access to everything VTpass offers:

    from vtpass.services import VTpass

    vt = VTpass()
    vt.airtime.buy("08011111111", 100, user=request.user)
    vt.data.plans("mtn"); vt.data.buy("08011111111", "mtn-10mb-100", user=user)
    vt.tv.verify("dstv", "1212121212"); vt.tv.renew("dstv", "1212121212", phone="0801...")
    vt.electricity.verify("ikedc", "1111111111111", "prepaid")
    vt.electricity.buy("ikedc", "1111111111111", "prepaid", 2000, phone="0801...")
    vt.education.waec_result_checker(phone="0801...", quantity=2)
    vt.internet.buy_smile(...); vt.internet.buy_spectranet(...)
    vt.insurance.options("brand"); vt.insurance.third_party_motor(...)
    vt.international.countries(); vt.international.buy(...)
    vt.bank.banks(); vt.bank.verify_account("gtb", "0123456789"); vt.bank.transfer(...)
    vt.insurance.personal_accident(...)
    vt.sms.send(["0801...", "0802..."], "Hello", sender="MyBrand")
    vt.purchase(service_id="any-new-service", phone=..., ...)   # anything else
    vt.requery(transaction); vt.balance()

Pass ``client=VTpassClient(...)`` to use different credentials (multi-tenant).
"""

from vtpass.services.airtime import AirtimeService
from vtpass.services.bank import BankTransferService
from vtpass.services.base import PurchaseEngine
from vtpass.services.cable import TVService
from vtpass.services.catalog import CatalogService
from vtpass.services.data import DataService
from vtpass.services.education import EducationService
from vtpass.services.electricity import ElectricityService
from vtpass.services.insurance import InsuranceService
from vtpass.services.internet import InternetService
from vtpass.services.international import InternationalAirtimeService
from vtpass.services.sms import SMSService
from vtpass.services.webhooks import WebhookService


class VTpass:
    def __init__(self, client=None, messaging_client=None, wallet_backend=None, pricing=None):
        self.engine = PurchaseEngine(client=client, wallet_backend=wallet_backend, pricing=pricing)
        self.airtime = AirtimeService(self.engine)
        self.data = DataService(self.engine)
        self.tv = TVService(self.engine)
        self.electricity = ElectricityService(self.engine)
        self.education = EducationService(self.engine)
        self.internet = InternetService(self.engine)
        self.insurance = InsuranceService(self.engine)
        self.international = InternationalAirtimeService(self.engine)
        self.bank = BankTransferService(self.engine)
        self.catalog = CatalogService(self.engine)
        self.webhooks = WebhookService(self.engine, self.catalog)
        self.sms = SMSService(messaging_client)

    @property
    def client(self):
        return self.engine.client

    # Generic operations ---------------------------------------------------------------
    def purchase(self, **kwargs):
        """Buy any product by ``service_id`` (see :meth:`PurchaseEngine.purchase`)."""
        return self.engine.purchase(**kwargs)

    def verify(self, service_id, billers_code, type=None, **extra):
        return self.engine.verify(service_id, billers_code, type=type, **extra)

    def quote(self, service_id, amount=None, variation_code=None, quantity=1, user=None, variation_params=None):
        """Price a purchase without buying: fee, discount, cashback and amount payable."""
        unit, _ = self.engine._resolve_amount(service_id, amount, variation_code, variation_params or {})
        return self.engine.pricing.quote(
            face_value=unit * (quantity or 1), service_id=service_id,
            category=self.engine.category_for(service_id), variation_code=variation_code or "",
            user=user, quantity=quantity or 1,
        )

    def requery(self, transaction):
        return self.engine.requery(transaction)

    def requery_pending(self, limit=None):
        return self.engine.requery_due(limit=limit)

    def balance(self):
        """VTpass merchant wallet balance."""
        return self.client.get_balance()


def get_vtpass(**kwargs):
    return VTpass(**kwargs)


__all__ = [
    "VTpass",
    "get_vtpass",
    "PurchaseEngine",
    "AirtimeService",
    "BankTransferService",
    "DataService",
    "TVService",
    "ElectricityService",
    "EducationService",
    "InternetService",
    "InsuranceService",
    "InternationalAirtimeService",
    "CatalogService",
    "WebhookService",
    "SMSService",
]
