"""
Background jobs as plain functions.

They run inline by default. With ``VTPASS["USE_CELERY"] = True`` the same
functions are executed by Celery workers through :mod:`vtpass.tasks`
(:func:`dispatch` picks the right path), so the package works with or without
Celery and with any other queue that can call a dotted function.
"""

import logging

from vtpass.settings import vtpass_settings

logger = logging.getLogger("vtpass")


def _vtpass():
    from vtpass.services import VTpass

    return VTpass()


def process_webhook(payload, event_id=None):
    from vtpass.models import WebhookEvent

    event = WebhookEvent.objects.filter(pk=event_id).first() if event_id else None
    return _vtpass().webhooks.process(payload, event=event)


def requery_transaction(transaction_id):
    from vtpass.models import Transaction

    txn = Transaction.objects.filter(pk=transaction_id).first()
    if txn is None or not txn.is_open:
        return None
    return _vtpass().requery(txn).status


def requery_pending(limit=None):
    return _vtpass().requery_pending(limit=limit)


def sync_catalog(categories=None, with_variations=True):
    return _vtpass().catalog.sync(categories=categories, with_variations=with_variations)


def sync_variations(service_id):
    return _vtpass().catalog.sync_variations(service_id)


def check_merchant_balance():
    from vtpass import signals
    from vtpass.utils import to_decimal

    balance = _vtpass().balance()
    threshold = to_decimal(vtpass_settings.LOW_BALANCE_THRESHOLD)
    if threshold is not None and balance < threshold:
        logger.warning("VTpass merchant balance %s is below %s", balance, threshold)
        signals.merchant_balance_low.send(sender=None, balance=balance, threshold=threshold)
    return str(balance)


def send_sms(recipients, message, sender=None, route=None, purpose=""):
    result = _vtpass().sms.send(recipients, message, sender=sender, route=route, purpose=purpose)
    return result.response_code


def send_notification(event, transaction_id):
    from vtpass.notifications import deliver

    return deliver(event, transaction_id)


def dispatch(name, *args, **kwargs):
    """Run job ``name`` on Celery when enabled, otherwise inline."""
    if vtpass_settings.USE_CELERY:
        try:
            from vtpass import tasks
        except ImportError:  # pragma: no cover - celery missing
            logger.error("VTPASS['USE_CELERY'] is True but Celery is not installed; running %s inline.", name)
        else:
            task = getattr(tasks, name)
            options = {"queue": vtpass_settings.CELERY_QUEUE} if vtpass_settings.CELERY_QUEUE else {}
            return task.apply_async(args=args, kwargs=kwargs, **options)
    return globals()[name](*args, **kwargs)
