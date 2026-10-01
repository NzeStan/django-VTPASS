"""Airtime VTU (MTN, Glo, Airtel, 9mobile)."""

from vtpass.constants import AIRTIME_SERVICE_IDS, Network
from vtpass.exceptions import VTpassValidationError
from vtpass.utils import detect_network, normalize_phone


class ProductService:
    """Base for product helpers. ``**options`` on every ``buy`` method are forwarded
    to :meth:`PurchaseEngine.purchase` (``user``, ``email``, ``idempotency_key``,
    ``metadata``, ``channel``, ``request``, ``charge_wallet``, ``save_beneficiary``...)."""

    def __init__(self, engine):
        self.engine = engine

    @property
    def client(self):
        return self.engine.client

    def plans(self, service_id, **params):
        return self.engine.get_variations(service_id, **params)


def resolve_network(phone, network=None):
    if network:
        try:
            return Network(str(network).lower().replace("etisalat", "9mobile"))
        except ValueError:
            raise VTpassValidationError(f"Unknown network {network!r}.", errors={"network": ["Invalid network."]})
    detected = detect_network(phone)
    if detected is None:
        raise VTpassValidationError(
            "Could not detect the network for this number; please choose one.",
            errors={"network": ["Required."]},
        )
    return detected


class AirtimeService(ProductService):
    def networks(self):
        return [{"id": n.value, "name": n.label, "service_id": AIRTIME_SERVICE_IDS[n]} for n in Network]

    def buy(self, phone, amount, network=None, service_id=None, **options):
        """
        Top up ``phone`` with ``amount`` naira. ``network`` is auto-detected
        from the number prefix when omitted.
        """
        phone = normalize_phone(phone)
        service_id = service_id or AIRTIME_SERVICE_IDS[resolve_network(phone, network)]
        return self.engine.purchase(service_id=service_id, phone=phone, amount=amount, **options)
