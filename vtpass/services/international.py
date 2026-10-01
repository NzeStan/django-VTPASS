"""International airtime, data and PINs (``foreign-airtime``)."""

from django.core.cache import cache

from vtpass.constants import ServiceID
from vtpass.exceptions import VTpassValidationError
from vtpass.services.airtime import ProductService
from vtpass.settings import vtpass_settings


class InternationalAirtimeService(ProductService):
    def _cached(self, key, loader):
        value = cache.get(key)
        if value is None:
            value = loader()
            cache.set(key, value, vtpass_settings.CATALOG_CACHE_TIMEOUT)
        return value

    def countries(self):
        return self._cached("vtpass:intl:countries", self.client.get_international_countries)

    def product_types(self, country_code):
        country_code = str(country_code).upper()
        return self._cached(
            f"vtpass:intl:types:{country_code}",
            lambda: self.client.get_international_product_types(country_code),
        )

    def operators(self, country_code, product_type_id):
        country_code = str(country_code).upper()
        return self._cached(
            f"vtpass:intl:operators:{country_code}:{product_type_id}",
            lambda: self.client.get_international_operators(country_code, product_type_id),
        )

    def variations(self, operator_id, product_type_id):
        return self.engine.get_variations(
            ServiceID.FOREIGN_AIRTIME, operator_id=operator_id, product_type_id=product_type_id
        )

    def buy(
        self,
        *,
        recipient,
        country_code,
        operator_id,
        product_type_id,
        variation_code,
        email,
        phone,
        amount=None,
        **options,
    ):
        """
        Send airtime/data abroad. ``recipient`` is the foreign number (with
        country code), ``phone`` is your customer's local number. ``amount``
        is required for flexible-price variations.
        """
        if not email:
            raise VTpassValidationError(
                "An email is required for international airtime.", errors={"email": ["Required."]}
            )
        options_extra = options.pop("extra", None) or {}
        return self.engine.purchase(
            service_id=ServiceID.FOREIGN_AIRTIME,
            phone=phone,
            billers_code="".join(ch for ch in str(recipient) if ch.isdigit()),
            variation_code=variation_code,
            amount=amount,
            email=email,
            variation_params={"operator_id": operator_id, "product_type_id": product_type_id},
            extra={
                "operator_id": operator_id,
                "country_code": str(country_code).upper(),
                "product_type_id": product_type_id,
                **options_extra,
            },
            **options,
        )
