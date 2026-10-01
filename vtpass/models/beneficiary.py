"""Saved billers (phones, meters, smartcards...) so customers can repeat purchases in one tap."""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _

from vtpass.models.base import TimeStampedModel


class Beneficiary(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vtpass_beneficiaries",
        verbose_name=_("user"),
    )
    category = models.CharField(_("category"), max_length=64, blank=True)
    service_id = models.CharField(_("service ID"), max_length=64)
    billers_code = models.CharField(_("billers code"), max_length=128)
    nickname = models.CharField(_("nickname"), max_length=64, blank=True)
    customer_name = models.CharField(_("verified customer name"), max_length=255, blank=True)
    extra = models.JSONField(
        _("extra data"), encoder=DjangoJSONEncoder, default=dict, blank=True, help_text=_("e.g. meter type")
    )
    last_used_at = models.DateTimeField(_("last used at"), null=True, blank=True)
    use_count = models.PositiveIntegerField(_("use count"), default=0)

    class Meta:
        verbose_name = _("beneficiary")
        verbose_name_plural = _("beneficiaries")
        ordering = ("-last_used_at", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "service_id", "billers_code"), name="vtpass_unique_beneficiary"
            ),
        ]

    def __str__(self):
        return self.nickname or f"{self.service_id} {self.billers_code}"
