"""Built-in signal receivers, connected in ``VTpassConfig.ready``. Each one is opt-in via settings."""

import logging

from django.dispatch import receiver

from vtpass import signals
from vtpass.jobs import dispatch
from vtpass.settings import vtpass_settings

logger = logging.getLogger("vtpass")


def _notify(event, transaction):
    config = vtpass_settings.NOTIFICATIONS
    if not config.get("ENABLED") or event not in config.get("EVENTS", []):
        return
    try:
        if config.get("ASYNC", True):
            dispatch("send_notification", event, transaction.pk)
        else:
            from vtpass.notifications import deliver

            deliver(event, transaction.pk)
    except Exception:
        logger.exception("Could not dispatch %s notification for %s", event, transaction.request_id)


@receiver(signals.transaction_successful, dispatch_uid="vtpass_notify_successful")
def notify_successful(sender, transaction, **kwargs):
    _notify("transaction.successful", transaction)


@receiver(signals.transaction_pending, dispatch_uid="vtpass_notify_pending")
def notify_pending(sender, transaction, **kwargs):
    _notify("transaction.pending", transaction)


@receiver(signals.transaction_failed, dispatch_uid="vtpass_notify_failed")
def notify_failed(sender, transaction, **kwargs):
    _notify("transaction.failed", transaction)


@receiver(signals.transaction_reversed, dispatch_uid="vtpass_notify_reversed")
def notify_reversed(sender, transaction, **kwargs):
    _notify("transaction.reversed", transaction)
