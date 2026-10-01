"""Bulk SMS through VTpass Messaging, with an optional audit log (``SMSMessage``)."""

import logging

from vtpass import signals
from vtpass.exceptions import VTpassError
from vtpass.messaging import MessagingClient
from vtpass.settings import vtpass_settings

logger = logging.getLogger("vtpass")


class SMSService:
    def __init__(self, client=None):
        self._client = client

    @property
    def client(self):
        if self._client is None:
            self._client = MessagingClient()
        return self._client

    def balance(self):
        """Remaining SMS units."""
        return self.client.balance()

    def send(self, recipients, message, sender=None, route=None, user=None, purpose="", **kwargs):
        """
        Send ``message`` to one or more recipients. Extra kwargs: ``dlr``,
        ``client_batch_id``, ``project_id``, ``api_version``.
        Returns :class:`~vtpass.messaging.SMSResult`; raises on rejection.
        """
        from vtpass.models import SMSMessage

        config = vtpass_settings.MESSAGING
        route = route or config["DEFAULT_ROUTE"]
        sender = sender or config["DEFAULT_SENDER"]
        formatted = None
        record = None
        try:
            formatted = self.client.format_recipients(recipients)
            result = self.client.send(formatted, message, sender=sender, route=route, **kwargs)
        except VTpassError as exc:
            if config.get("LOG_MESSAGES") and formatted:
                SMSMessage.objects.create(
                    user=user if getattr(user, "pk", None) else None, sender=sender or "",
                    recipients=formatted, recipient_count=formatted.count(",") + 1, message=message,
                    route=route, state=SMSMessage.FAILED, response_code=str(getattr(exc, "code", "") or "")[:8],
                    response=_jsonable(getattr(exc, "response", None)), error=str(exc), purpose=purpose,
                    client_batch_id=str(kwargs.get("client_batch_id") or ""),
                )
            raise
        if config.get("LOG_MESSAGES"):
            record = SMSMessage.objects.create(
                user=user if getattr(user, "pk", None) else None, sender=sender, recipients=formatted,
                recipient_count=formatted.count(",") + 1, message=message, route=route,
                state=SMSMessage.SENT, response_code=result.response_code[:8], batch_id=result.batch_id or "",
                client_batch_id=str(kwargs.get("client_batch_id") or ""), response=_jsonable(result.raw),
                purpose=purpose,
            )
        signals.sms_sent.send(sender=self.__class__, message=record, result=result)
        return result


def _jsonable(value):
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    return {"raw": str(value)[:5000]}
