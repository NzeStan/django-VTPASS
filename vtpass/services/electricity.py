"""Electricity bills for all 12 distribution companies (prepaid tokens and postpaid)."""

from vtpass.constants import ELECTRICITY_SERVICE_IDS, MeterType, ServiceID
from vtpass.exceptions import VTpassValidationError
from vtpass.services.airtime import ProductService

DISCO_ALIASES = {
    "ikedc": ServiceID.IKEJA, "ikeja": ServiceID.IKEJA,
    "ekedc": ServiceID.EKO, "eko": ServiceID.EKO,
    "kedco": ServiceID.KANO, "kano": ServiceID.KANO,
    "phed": ServiceID.PORT_HARCOURT, "portharcourt": ServiceID.PORT_HARCOURT,
    "port-harcourt": ServiceID.PORT_HARCOURT,
    "jed": ServiceID.JOS, "jos": ServiceID.JOS,
    "ibedc": ServiceID.IBADAN, "ibadan": ServiceID.IBADAN,
    "kaedco": ServiceID.KADUNA, "kaduna": ServiceID.KADUNA,
    "aedc": ServiceID.ABUJA, "abuja": ServiceID.ABUJA,
    "eedc": ServiceID.ENUGU, "enugu": ServiceID.ENUGU,
    "bedc": ServiceID.BENIN, "benin": ServiceID.BENIN,
    "aba": ServiceID.ABA, "apl": ServiceID.ABA,
    "yedc": ServiceID.YOLA, "yola": ServiceID.YOLA,
}


def resolve_disco(disco):
    key = str(disco).lower().strip()
    if key in ELECTRICITY_SERVICE_IDS:
        return key
    if key in DISCO_ALIASES:
        return DISCO_ALIASES[key]
    raise VTpassValidationError(f"Unknown electricity company {disco!r}.", errors={"disco": ["Invalid."]})


def resolve_meter_type(meter_type):
    try:
        return MeterType(str(meter_type).lower())
    except ValueError:
        raise VTpassValidationError("Meter type must be prepaid or postpaid.", errors={"meter_type": ["Invalid."]})


class ElectricityService(ProductService):
    def discos(self):
        return [{"service_id": sid, "name": name} for sid, name in ELECTRICITY_SERVICE_IDS.items()]

    def verify(self, disco, meter_number, meter_type):
        """
        Validate a meter. Returns ``Customer_Name``, ``Address``,
        ``Meter_Number``, ``Customer_Account_Type`` (MD/NMD), minimum amount, etc.
        """
        return self.engine.verify(resolve_disco(disco), meter_number, type=resolve_meter_type(meter_type).value)

    def buy(self, disco, meter_number, meter_type, amount, phone, **options):
        """
        Pay for electricity. For prepaid meters the token is in
        ``transaction.token`` / ``transaction.vend_details`` once successful.
        """
        return self.engine.purchase(
            service_id=resolve_disco(disco),
            phone=phone,
            billers_code=meter_number,
            variation_code=resolve_meter_type(meter_type).value,
            lookup_variation=False,
            amount=amount,
            **options,
        )
