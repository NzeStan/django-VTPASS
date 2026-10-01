"""Mobile data bundles (MTN, Glo, Glo SME, Airtel, 9mobile)."""

from vtpass.constants import DATA_SERVICE_IDS, Network, ServiceID
from vtpass.services.airtime import ProductService, resolve_network
from vtpass.utils import normalize_phone


class DataService(ProductService):
    def networks(self):
        items = [{"id": n.value, "name": n.label, "service_id": DATA_SERVICE_IDS[n]} for n in Network]
        items.append({"id": "glo-sme", "name": "Glo SME", "service_id": ServiceID.GLO_SME_DATA})
        return items

    def service_id_for(self, network=None, phone=None, sme=False):
        resolved = resolve_network(phone, network)
        if sme and resolved == Network.GLO:
            return ServiceID.GLO_SME_DATA
        return DATA_SERVICE_IDS[resolved]

    def plans(self, network=None, service_id=None, phone=None, sme=False):
        """Data plans for a network (or explicit ``service_id``)."""
        return self.engine.get_variations(service_id or self.service_id_for(network, phone, sme))

    def buy(self, phone, variation_code, network=None, service_id=None, billers_code=None, amount=None,
            sme=False, **options):
        """Buy data plan ``variation_code`` for ``phone`` (the plan sets the price)."""
        phone = normalize_phone(phone)
        service_id = service_id or self.service_id_for(network, phone, sme)
        return self.engine.purchase(
            service_id=service_id,
            phone=phone,
            billers_code=normalize_phone(billers_code) if billers_code else phone,
            variation_code=variation_code,
            amount=amount,
            **options,
        )
