"""Synchronise the VTpass catalogue (categories, services, plans) into the local database."""

import logging

from django.core.cache import cache
from django.db import transaction as db_transaction
from django.utils import timezone

from vtpass import signals
from vtpass.exceptions import VTpassError
from vtpass.utils import to_decimal

logger = logging.getLogger("vtpass")


class CatalogService:
    def __init__(self, engine):
        self.engine = engine

    @property
    def client(self):
        return self.engine.client

    # ---- read ----------------------------------------------------------------------
    def categories(self, live=False):
        from vtpass.models import ServiceCategory

        if not live:
            rows = list(ServiceCategory.objects.filter(is_active=True).values("identifier", "name"))
            if rows:
                return rows
        return self.client.get_service_categories()

    def services(self, category, live=False):
        from vtpass.models import Service

        if not live:
            rows = Service.objects.filter(category__identifier=category, is_active=True)
            if rows.exists():
                return [
                    {
                        "serviceID": s.service_id, "name": s.name, "image": s.image,
                        "minimium_amount": s.minimum_amount, "maximum_amount": s.maximum_amount,
                        "convinience_fee": s.convenience_fee, "product_type": s.product_type,
                    }
                    for s in rows
                ]
        return self.client.get_services(category)

    def variations(self, service_id, **params):
        return self.engine.get_variations(service_id, **params)

    def options(self, service_id, name):
        return self.client.get_options(service_id, name)

    # ---- sync ----------------------------------------------------------------------
    def sync(self, categories=None, with_variations=True):
        """
        Pull categories, services and (optionally) variations from VTpass.
        Items that disappeared upstream are deactivated, never deleted, so
        historical transactions keep their references.
        """
        from vtpass.models import Service, ServiceCategory

        stats = {"categories": 0, "services": 0, "variations": 0}
        remote_categories = self.client.get_service_categories()
        for position, item in enumerate(remote_categories):
            identifier = item.get("identifier")
            if not identifier or (categories and identifier not in categories):
                continue
            category, _ = ServiceCategory.objects.update_or_create(
                identifier=identifier,
                defaults={"name": item.get("name") or identifier, "is_active": True, "position": position},
            )
            stats["categories"] += 1
            try:
                remote_services = self.client.get_services(identifier)
            except VTpassError as exc:
                logger.warning("Could not fetch services for %s: %s", identifier, exc)
                continue
            seen = []
            for svc_position, svc in enumerate(remote_services):
                service_id = svc.get("serviceID")
                if not service_id:
                    continue
                seen.append(service_id)
                service, _ = Service.objects.update_or_create(
                    service_id=service_id,
                    defaults={
                        "category": category,
                        "name": svc.get("name") or service_id,
                        "image": (svc.get("image") or "")[:500],
                        "minimum_amount": to_decimal(svc.get("minimium_amount", svc.get("minimum_amount"))),
                        "maximum_amount": to_decimal(svc.get("maximum_amount")),
                        "convenience_fee": str(svc.get("convinience_fee") or "")[:64],
                        "product_type": str(svc.get("product_type") or "")[:32],
                        "is_active": True,
                        "position": svc_position,
                        "extra": {k: v for k, v in svc.items() if k not in ("serviceID", "name")},
                    },
                )
                stats["services"] += 1
                if with_variations:
                    try:
                        stats["variations"] += self.sync_variations(service_id)
                    except VTpassError as exc:
                        logger.warning("Could not fetch variations for %s: %s", service_id, exc)
            Service.objects.filter(category=category).exclude(service_id__in=seen).update(is_active=False)

        signals.catalog_synced.send(sender=self.__class__, **stats)
        return stats

    def sync_variations(self, service_id, content=None):
        """Refresh the plans for one service (from ``content`` if given, else the API)."""
        from vtpass.models import Service, Variation

        if content is None:
            content = self.client.get_variations(service_id)
        variations = content.get("variations") or content.get("varations") or []
        service = Service.objects.filter(service_id=service_id).first()
        if service is None:
            from vtpass.models import ServiceCategory

            category_id = self.engine.category_for(service_id) or "other-services"
            category, _ = ServiceCategory.objects.get_or_create(
                identifier=category_id, defaults={"name": category_id.replace("-", " ").title()}
            )
            service = Service.objects.create(
                service_id=service_id, name=content.get("ServiceName") or service_id, category=category
            )
        with db_transaction.atomic():
            codes = []
            for item in variations:
                code = item.get("variation_code")
                if code in (None, ""):
                    continue
                code = str(code)
                codes.append(code)
                Variation.objects.update_or_create(
                    service=service,
                    variation_code=code,
                    defaults={
                        "name": str(item.get("name") or code)[:255],
                        "amount": to_decimal(item.get("variation_amount")),
                        "fixed_price": str(item.get("fixedPrice", "Yes")).lower() in ("yes", "true", "1"),
                        "is_active": True,
                        "extra": {
                            k: v for k, v in item.items()
                            if k not in ("variation_code", "name", "variation_amount", "fixedPrice")
                        },
                    },
                )
            service.variations.exclude(variation_code__in=codes).update(is_active=False)
            if content.get("convinience_fee") is not None:
                service.convenience_fee = str(content["convinience_fee"])[:64]
            service.variations_synced_at = timezone.now()
            service.save(update_fields=["convenience_fee", "variations_synced_at", "updated_at"])
        # Unparameterised lookups now read the synced rows; drop the stale API copy.
        cache.delete(f"vtpass:variations:{service_id}:")
        return len(codes)
