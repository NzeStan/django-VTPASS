"""
Constants describing the VTpass platform: categories, service IDs, response
codes, transaction statuses and sandbox test values.

Service IDs listed here are the ones documented by VTpass. Any other service ID
VTpass adds later still works through the generic purchase flow, because the
package never restricts purchases to this list.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Category(models.TextChoices):
    """VTpass service category identifiers (``/api/service-categories``)."""

    AIRTIME = "airtime", _("Airtime Recharge")
    DATA = "data", _("Data Services")
    TV = "tv-subscription", _("TV Subscription")
    ELECTRICITY = "electricity-bill", _("Electricity Bill")
    EDUCATION = "education", _("Education")
    INSURANCE = "insurance", _("Insurance")
    INTERNATIONAL_AIRTIME = "international-airtime", _("International Airtime")
    BANK_TRANSFER = "bank-transfer", _("Bank Transfer")
    OTHER = "other-services", _("Other Services")


class Status(models.TextChoices):
    """Lifecycle of a transaction recorded by this package."""

    INITIATED = "initiated", _("Initiated")
    PENDING = "pending", _("Pending")
    SUCCESSFUL = "successful", _("Successful")
    FAILED = "failed", _("Failed")
    REVERSED = "reversed", _("Reversed")

    @classmethod
    def terminal(cls):
        return {cls.SUCCESSFUL, cls.FAILED, cls.REVERSED}

    @classmethod
    def open(cls):
        return {cls.INITIATED, cls.PENDING}


# Allowed status moves. A successful transaction may still be reversed by
# VTpass afterwards; failed and reversed transactions are final.
STATUS_TRANSITIONS = {
    Status.INITIATED: {Status.PENDING, Status.SUCCESSFUL, Status.FAILED, Status.REVERSED},
    Status.PENDING: {Status.SUCCESSFUL, Status.FAILED, Status.REVERSED},
    Status.SUCCESSFUL: {Status.REVERSED},
    Status.FAILED: set(),
    Status.REVERSED: set(),
}


class ServiceID:
    """Documented VTpass ``serviceID`` values."""

    # Airtime
    MTN = "mtn"
    GLO = "glo"
    AIRTEL = "airtel"
    NINE_MOBILE = "etisalat"
    FOREIGN_AIRTIME = "foreign-airtime"

    # Data
    MTN_DATA = "mtn-data"
    GLO_DATA = "glo-data"
    GLO_SME_DATA = "glo-sme-data"
    AIRTEL_DATA = "airtel-data"
    NINE_MOBILE_DATA = "etisalat-data"
    SMILE = "smile-direct"
    SPECTRANET = "spectranet"

    # TV
    DSTV = "dstv"
    GOTV = "gotv"
    STARTIMES = "startimes"
    SHOWMAX = "showmax"

    # Electricity
    IKEJA = "ikeja-electric"
    EKO = "eko-electric"
    KANO = "kano-electric"
    PORT_HARCOURT = "portharcourt-electric"
    JOS = "jos-electric"
    IBADAN = "ibadan-electric"
    KADUNA = "kaduna-electric"
    ABUJA = "abuja-electric"
    ENUGU = "enugu-electric"
    BENIN = "benin-electric"
    ABA = "aba-electric"
    YOLA = "yola-electric"

    # Education
    WAEC_RESULT_CHECKER = "waec"
    WAEC_REGISTRATION = "waec-registration"
    JAMB = "jamb"

    # Insurance
    THIRD_PARTY_MOTOR = "ui-insure"
    PERSONAL_ACCIDENT = "personal-accident-insurance"

    # Funds
    BANK_DEPOSIT = "bank-deposit"


class Network(models.TextChoices):
    """Nigerian mobile networks."""

    MTN = "mtn", "MTN"
    GLO = "glo", "Glo"
    AIRTEL = "airtel", "Airtel"
    NINE_MOBILE = "9mobile", "9mobile"


AIRTIME_SERVICE_IDS = {
    Network.MTN: ServiceID.MTN,
    Network.GLO: ServiceID.GLO,
    Network.AIRTEL: ServiceID.AIRTEL,
    Network.NINE_MOBILE: ServiceID.NINE_MOBILE,
}

DATA_SERVICE_IDS = {
    Network.MTN: ServiceID.MTN_DATA,
    Network.GLO: ServiceID.GLO_DATA,
    Network.AIRTEL: ServiceID.AIRTEL_DATA,
    Network.NINE_MOBILE: ServiceID.NINE_MOBILE_DATA,
}

TV_SERVICE_IDS = (ServiceID.DSTV, ServiceID.GOTV, ServiceID.STARTIMES, ServiceID.SHOWMAX)

ELECTRICITY_SERVICE_IDS = {
    ServiceID.IKEJA: "Ikeja Electric (IKEDC)",
    ServiceID.EKO: "Eko Electric (EKEDC)",
    ServiceID.KANO: "Kano Electric (KEDCO)",
    ServiceID.PORT_HARCOURT: "Port Harcourt Electric (PHED)",
    ServiceID.JOS: "Jos Electric (JED)",
    ServiceID.IBADAN: "Ibadan Electric (IBEDC)",
    ServiceID.KADUNA: "Kaduna Electric (KAEDCO)",
    ServiceID.ABUJA: "Abuja Electric (AEDC)",
    ServiceID.ENUGU: "Enugu Electric (EEDC)",
    ServiceID.BENIN: "Benin Electric (BEDC)",
    ServiceID.ABA: "Aba Electric (ABA)",
    ServiceID.YOLA: "Yola Electric (YEDC)",
}

# Best-effort mapping used when the local catalogue has not been synced yet.
SERVICE_CATEGORY_HINTS = {
    **{sid: Category.AIRTIME for sid in AIRTIME_SERVICE_IDS.values()},
    **{sid: Category.DATA for sid in DATA_SERVICE_IDS.values()},
    ServiceID.GLO_SME_DATA: Category.DATA,
    ServiceID.SMILE: Category.DATA,
    ServiceID.SPECTRANET: Category.DATA,
    ServiceID.FOREIGN_AIRTIME: Category.INTERNATIONAL_AIRTIME,
    **{sid: Category.TV for sid in TV_SERVICE_IDS},
    **{sid: Category.ELECTRICITY for sid in ELECTRICITY_SERVICE_IDS},
    ServiceID.WAEC_RESULT_CHECKER: Category.EDUCATION,
    ServiceID.WAEC_REGISTRATION: Category.EDUCATION,
    ServiceID.JAMB: Category.EDUCATION,
    ServiceID.THIRD_PARTY_MOTOR: Category.INSURANCE,
    ServiceID.PERSONAL_ACCIDENT: Category.INSURANCE,
    ServiceID.BANK_DEPOSIT: Category.BANK_TRANSFER,
}


class MeterType(models.TextChoices):
    PREPAID = "prepaid", _("Prepaid")
    POSTPAID = "postpaid", _("Postpaid")


class SubscriptionType(models.TextChoices):
    """DSTV/GOTV purchase mode."""

    CHANGE = "change", _("Change / new bouquet")
    RENEW = "renew", _("Renew current bouquet")


class InsuranceOption:
    """Universal Insurance option lookups (``/api/universal-insurance/options/...``)."""

    COLOR = "color"
    ENGINE_CAPACITY = "engine-capacity"
    STATE = "state"
    LGA = "lga"  # requires a state code
    BRAND = "brand"
    MODEL = "model"  # requires a vehicle make (brand) code

    ALL = (COLOR, ENGINE_CAPACITY, STATE, LGA, BRAND, MODEL)
    REQUIRES_PARENT = (LGA, MODEL)


class ResponseCode:
    """Billing API response codes."""

    PROCESSED = "000"
    TRANSACTION_QUERY = "001"
    VARIATION_CODE_NOT_FOUND = "010"
    INVALID_ARGUMENTS = "011"
    PRODUCT_NOT_FOUND = "012"
    BELOW_MINIMUM_AMOUNT = "013"
    REQUEST_ID_EXISTS = "014"
    INVALID_REQUEST_ID = "015"
    TRANSACTION_FAILED = "016"
    ABOVE_MAXIMUM_AMOUNT = "017"
    LOW_WALLET_BALANCE = "018"
    LIKELY_DUPLICATE = "019"
    BILLER_CONFIRMED = "020"
    ACCOUNT_LOCKED = "021"
    ACCOUNT_SUSPENDED = "022"
    API_ACCESS_DISABLED = "023"
    ACCOUNT_INACTIVE = "024"
    RECIPIENT_BANK_INVALID = "025"
    RECIPIENT_ACCOUNT_UNVERIFIED = "026"
    IP_NOT_WHITELISTED = "027"
    PRODUCT_NOT_WHITELISTED = "028"
    BILLER_UNREACHABLE = "030"
    BELOW_MINIMUM_QUANTITY = "031"
    ABOVE_MAXIMUM_QUANTITY = "032"
    SERVICE_SUSPENDED = "034"
    SERVICE_INACTIVE = "035"
    TRANSACTION_REVERSAL = "040"
    TRANSACTION_RESOLVED = "044"
    SYSTEM_ERROR = "083"
    IMPROPER_REQUEST_ID = "085"
    INVALID_CREDENTIALS = "087"
    REQUEST_PROCESSING = "089"
    TRANSACTION_NOT_PROCESSED = "091"
    TRANSACTION_PROCESSING = "099"

    DESCRIPTIONS = {
        "000": "Transaction processed",
        "001": "Transaction query",
        "010": "Variation code does not exist",
        "011": "Invalid arguments",
        "012": "Product does not exist",
        "013": "Below minimum amount allowed",
        "014": "Request ID already exists",
        "015": "Invalid request ID",
        "016": "Transaction failed",
        "017": "Above maximum amount allowed",
        "018": "Low wallet balance",
        "019": "Likely duplicate transaction",
        "020": "Biller confirmed",
        "021": "Account locked",
        "022": "Account suspended",
        "023": "API access not enabled for user",
        "024": "Account inactive",
        "025": "Recipient bank invalid",
        "026": "Recipient account could not be verified",
        "027": "IP not whitelisted, contact support",
        "028": "Product is not whitelisted on your account",
        "030": "Biller not reachable at this point",
        "031": "Below minimum quantity allowed",
        "032": "Above maximum quantity allowed",
        "034": "Service suspended",
        "035": "Service inactive",
        "040": "Transaction reversal",
        "044": "Transaction resolved",
        "083": "System error",
        "085": "Improper request ID",
        "087": "Invalid credentials",
        "089": "Request is processing",
        "091": "Transaction not processed",
        "099": "Transaction is processing",
    }

    # The outcome is unknown: keep the transaction open and requery later.
    PENDING_CODES = {TRANSACTION_PROCESSING, REQUEST_PROCESSING, REQUEST_ID_EXISTS, SYSTEM_ERROR}
    # Problems with the merchant account/configuration, not the customer's input.
    MERCHANT_ERROR_CODES = {
        LOW_WALLET_BALANCE, ACCOUNT_LOCKED, ACCOUNT_SUSPENDED, API_ACCESS_DISABLED,
        ACCOUNT_INACTIVE, IP_NOT_WHITELISTED, PRODUCT_NOT_WHITELISTED,
        IMPROPER_REQUEST_ID, INVALID_CREDENTIALS,
    }


class VTpassTransactionStatus:
    """Values of ``content.transactions.status`` in VTpass responses."""

    INITIATED = "initiated"
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    REVERSED = "reversed"


class SMSRoute(models.TextChoices):
    """VTpass Messaging routes."""

    NORMAL = "normal", _("Normal")
    DND = "dnd", _("DND")
    DND_FALLBACK = "dnd-fallback", _("DND fallback")
    SIMHOST = "simhost", _("SIMHOST")
    SIMHOST_FALLBACK = "simhost-fallback", _("SIMHOST DND fallback")


class SMSResponseCode:
    PROCESSED = "TG00"
    DESCRIPTIONS = {
        "TG00": "Message processed",
        "TG11": "Invalid authentication credentials",
        "TG12": "Missing username",
        "TG13": "Missing password",
        "TG14": "Missing recipients",
        "TG15": "Missing message",
        "TG16": "Missing sender ID",
        "TG17": "Insufficient SMS unit balance",
        "TG18": "Prohibited content",
        "TG19": "Prohibited content",
        "TG20": "Recipient limit exceeded",
    }


class SMSMessageStatus:
    """Per-recipient status codes returned by the Messaging API."""

    SENT = "0000"
    DELIVERED = "1111"
    REJECTED = "2222"
    DND_SENT = "0014"
    DND_REJECTED = "3333"


class WebhookType:
    TRANSACTION_UPDATE = "transaction-update"
    VARIATIONS_UPDATE = "variations-update"


class Sandbox:
    """Values that trigger specific outcomes on sandbox.vtpass.com."""

    PHONE_SUCCESS = "08011111111"
    PHONE_PENDING = "201000000000"
    PHONE_UNEXPECTED = "500000000000"
    PHONE_NO_RESPONSE = "400000000000"
    PHONE_TIMEOUT = "300000000000"
    SMARTCARD_SUCCESS = "1212121212"
    SPECTRANET_SUCCESS = "1212121212"
    METER_PREPAID = "1111111111111"
    METER_POSTPAID = "1010101010101"
    JAMB_PROFILE_ID = "0123456789"
    SMILE_EMAIL = "tester@sandbox.com"
    BANK_ACCOUNT = "1234567890"


class WalletEntryKind(models.TextChoices):
    FUNDING = "funding", _("Funding")
    PURCHASE = "purchase", _("Purchase")
    REFUND = "refund", _("Refund")
    CASHBACK = "cashback", _("Cashback")
    ADJUSTMENT = "adjustment", _("Adjustment")


class AmountType(models.TextChoices):
    FLAT = "flat", _("Flat amount")
    PERCENT = "percent", _("Percentage")
