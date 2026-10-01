"""Notification backends. Each returns True when something was sent."""

import logging

from vtpass.notifications import get_template, render
from vtpass.settings import vtpass_settings

logger = logging.getLogger("vtpass")


class BaseNotificationBackend:
    channel = None

    def send(self, event, transaction, context) -> bool:
        raise NotImplementedError

    def template(self, event, key=None):
        return get_template(event, key or self.channel)


class SMSBackend(BaseNotificationBackend):
    """Text the customer's phone through VTpass Messaging (uses your SMS units)."""

    channel = "sms"

    def get_recipient(self, transaction):
        return transaction.phone

    def send(self, event, transaction, context):
        recipient = self.get_recipient(transaction)
        template = self.template(event)
        if not recipient or not template:
            return False
        from vtpass.services.sms import SMSService

        config = vtpass_settings.NOTIFICATIONS
        SMSService().send(
            recipient, render(template, context)[:918],
            sender=config.get("SMS_SENDER") or None,
            route=config.get("SMS_ROUTE") or None,
            user=transaction.user,
            purpose="notification",
        )
        return True


class EmailBackend(BaseNotificationBackend):
    """Email the customer with Django's configured email backend."""

    channel = "email"

    def get_recipient(self, transaction):
        if transaction.email:
            return transaction.email
        return getattr(transaction.user, "email", "") if transaction.user else ""

    def send(self, event, transaction, context):
        from django.core.mail import send_mail

        recipient = self.get_recipient(transaction)
        subject, body = self.template(event, "subject"), self.template(event, "body")
        if not recipient or not body:
            return False
        send_mail(
            render(subject, context),
            render(body, context),
            vtpass_settings.NOTIFICATIONS.get("EMAIL_FROM") or None,
            [recipient],
        )
        return True


class LoggingBackend(BaseNotificationBackend):
    """Writes notifications to the ``vtpass`` logger (handy in development)."""

    channel = "sms"

    def send(self, event, transaction, context):
        logger.info("[notification] %s -> %s: %s", event, transaction.phone, render(self.template(event), context))
        return True
