"""Record of SMS sent through VTpass Messaging."""

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.utils.translation import gettext_lazy as _

from vtpass.constants import SMSRoute
from vtpass.models.base import TimeStampedModel


class SMSMessage(TimeStampedModel):
    SENT = "sent"
    FAILED = "failed"
    STATES = ((SENT, _("Sent")), (FAILED, _("Failed")))

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="vtpass_sms_messages", verbose_name=_("sent by"),
    )
    sender = models.CharField(_("sender"), max_length=32)
    recipients = models.TextField(_("recipients"))
    recipient_count = models.PositiveIntegerField(_("recipient count"), default=0)
    message = models.TextField(_("message"))
    route = models.CharField(_("route"), max_length=24, choices=SMSRoute.choices, default=SMSRoute.NORMAL)
    state = models.CharField(_("state"), max_length=8, choices=STATES, default=SENT)
    response_code = models.CharField(_("response code"), max_length=8, blank=True)
    batch_id = models.CharField(_("batch ID"), max_length=64, blank=True, db_index=True)
    client_batch_id = models.CharField(_("client batch ID"), max_length=64, blank=True)
    response = models.JSONField(_("response"), encoder=DjangoJSONEncoder, default=dict, blank=True)
    error = models.TextField(_("error"), blank=True)
    purpose = models.CharField(_("purpose"), max_length=64, blank=True,
                               help_text=_("e.g. otp, notification, marketing"))

    class Meta:
        verbose_name = _("SMS message")
        verbose_name_plural = _("SMS messages")
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.sender} -> {self.recipient_count} recipient(s) [{self.state}]"
