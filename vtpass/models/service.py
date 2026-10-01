"""
Local copy of the VTpass product catalogue.

Synced from the API with ``python manage.py vtpass_sync_catalog`` (or the
``sync_catalog`` Celery task) and kept fresh automatically by the
``variations-update`` webhook. Purchases do not require a synced catalogue;
it exists so you can list products quickly, add your own display data
(ordering, enabling/disabling products) and price plans without hitting
VTpass on every request.
"""

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _

from vtpass.models.base import TimeStampedModel


class ServiceCategory(TimeStampedModel):
    identifier = models.CharField(_("identifier"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=128)
    is_active = models.BooleanField(_("active"), default=True)
    position = models.PositiveIntegerField(_("position"), default=0)

    class Meta:
        verbose_name = _("service category")
        verbose_name_plural = _("service categories")
        ordering = ("position", "name")

    def __str__(self):
        return self.name


class Service(TimeStampedModel):
    category = models.ForeignKey(
        ServiceCategory, related_name="services", on_delete=models.CASCADE, verbose_name=_("category")
    )
    service_id = models.CharField(_("VTpass service ID"), max_length=64, unique=True)
    name = models.CharField(_("name"), max_length=255)
    image = models.URLField(_("image URL"), blank=True, max_length=500)
    minimum_amount = models.DecimalField(_("minimum amount"), max_digits=14, decimal_places=2, null=True, blank=True)
    maximum_amount = models.DecimalField(_("maximum amount"), max_digits=14, decimal_places=2, null=True, blank=True)
    convenience_fee = models.CharField(_("VTpass convenience fee"), max_length=64, blank=True)
    product_type = models.CharField(_("product type"), max_length=32, blank=True)
    is_active = models.BooleanField(_("active"), default=True)
    position = models.PositiveIntegerField(_("position"), default=0)
    extra = models.JSONField(_("extra data"), encoder=DjangoJSONEncoder, default=dict, blank=True)
    variations_synced_at = models.DateTimeField(_("variations synced at"), null=True, blank=True)

    class Meta:
        verbose_name = _("service")
        verbose_name_plural = _("services")
        ordering = ("category__position", "position", "name")

    def __str__(self):
        return f"{self.name} ({self.service_id})"


class Variation(TimeStampedModel):
    service = models.ForeignKey(
        Service, related_name="variations", on_delete=models.CASCADE, verbose_name=_("service")
    )
    variation_code = models.CharField(_("variation code"), max_length=128)
    name = models.CharField(_("name"), max_length=255)
    amount = models.DecimalField(_("amount"), max_digits=14, decimal_places=2, null=True, blank=True)
    fixed_price = models.BooleanField(_("fixed price"), default=True)
    is_active = models.BooleanField(_("active"), default=True)
    extra = models.JSONField(_("extra data"), encoder=DjangoJSONEncoder, default=dict, blank=True)

    class Meta:
        verbose_name = _("variation")
        verbose_name_plural = _("variations")
        ordering = ("service", "amount", "name")
        constraints = [
            models.UniqueConstraint(fields=("service", "variation_code"), name="vtpass_unique_variation"),
        ]

    def __str__(self):
        return f"{self.name} ({self.variation_code})"
