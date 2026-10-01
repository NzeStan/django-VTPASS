"""
Celery tasks (optional – requires ``pip install django-vtpass[celery]``).

Suggested beat schedule::

    CELERY_BEAT_SCHEDULE = {
        "vtpass-requery-pending": {"task": "vtpass.requery_pending", "schedule": 60},
        "vtpass-sync-catalog": {"task": "vtpass.sync_catalog", "schedule": 6 * 60 * 60},
        "vtpass-check-balance": {"task": "vtpass.check_merchant_balance", "schedule": 15 * 60},
    }
"""

from celery import shared_task

from vtpass import jobs

_RETRY = {"autoretry_for": (Exception,), "retry_backoff": True, "retry_backoff_max": 600, "max_retries": 5}


@shared_task(name="vtpass.process_webhook", **_RETRY)
def process_webhook(payload, event_id=None):
    return jobs.process_webhook(payload, event_id)


@shared_task(name="vtpass.requery_transaction", **_RETRY)
def requery_transaction(transaction_id):
    return jobs.requery_transaction(transaction_id)


@shared_task(name="vtpass.requery_pending")
def requery_pending(limit=None):
    return jobs.requery_pending(limit)


@shared_task(name="vtpass.sync_catalog")
def sync_catalog(categories=None, with_variations=True):
    return jobs.sync_catalog(categories, with_variations)


@shared_task(name="vtpass.sync_variations", **_RETRY)
def sync_variations(service_id):
    return jobs.sync_variations(service_id)


@shared_task(name="vtpass.check_merchant_balance")
def check_merchant_balance():
    return jobs.check_merchant_balance()


@shared_task(name="vtpass.send_sms", autoretry_for=(ConnectionError,), retry_backoff=True, max_retries=3)
def send_sms(recipients, message, sender=None, route=None, purpose=""):
    return jobs.send_sms(recipients, message, sender, route, purpose)


@shared_task(name="vtpass.send_notification", **_RETRY)
def send_notification(event, transaction_id):
    return jobs.send_notification(event, transaction_id)
