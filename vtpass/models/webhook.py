"""Audit log of callbacks received from VTpass."""

from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _

from vtpass.models.base import TimeStampedModel


class WebhookEvent(TimeStampedModel):
    RECEIVED = "received"
    PROCESSED = "processed"
    IGNORED = "ignored"
    FAILED = "failed"
    STATES = (
        (RECEIVED, _("Received")),
        (PROCESSED, _("Processed")),
        (IGNORED, _("Ignored")),
        (FAILED, _("Failed")),
    )

    event_type = models.CharField(_("type"), max_length=64, db_index=True)
    request_id = models.CharField(_("request ID"), max_length=64, blank=True, db_index=True)
    service_id = models.CharField(_("service ID"), max_length=64, blank=True)
    payload = models.JSONField(_("payload"), encoder=DjangoJSONEncoder, default=dict)
    fingerprint = models.CharField(_("payload fingerprint"), max_length=64, db_index=True)
    state = models.CharField(_("state"), max_length=16, choices=STATES, default=RECEIVED)
    attempts = models.PositiveIntegerField(_("deliveries received"), default=1)
    error = models.TextField(_("error"), blank=True)
    remote_ip = models.GenericIPAddressField(_("remote IP"), null=True, blank=True)
    processed_at = models.DateTimeField(_("processed at"), null=True, blank=True)

    class Meta:
        verbose_name = _("webhook event")
        verbose_name_plural = _("webhook events")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.event_type} {self.request_id or self.service_id}"
