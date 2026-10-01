"""
Processing of VTpass callbacks (``transaction-update`` and ``variations-update``).

The HTTP view acknowledges immediately (``{"response": "success"}``) and hands
the payload here, synchronously or through Celery. Because VTpass callbacks
are not signed, transaction updates are confirmed with a requery by default
(``WEBHOOK["VERIFY_WITH_REQUERY"]``) before any money moves.
"""

import hashlib
import json
import logging

from django.utils import timezone

from vtpass import signals
from vtpass.client import VTpassResponse
from vtpass.constants import WebhookType
from vtpass.settings import vtpass_settings

logger = logging.getLogger("vtpass")


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def record_event(payload, remote_ip=None):
    """Store (or deduplicate) an incoming event. Returns the WebhookEvent or None when storage is off."""
    from vtpass.models import WebhookEvent

    if not vtpass_settings.WEBHOOK["STORE_EVENTS"]:
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    digest = fingerprint(payload)
    existing = WebhookEvent.objects.filter(fingerprint=digest).order_by("-created_at").first()
    if existing is not None:
        WebhookEvent.objects.filter(pk=existing.pk).update(attempts=existing.attempts + 1)
        existing.attempts += 1
        return existing
    return WebhookEvent.objects.create(
        event_type=str(payload.get("type", ""))[:64],
        request_id=str(data.get("requestId") or "")[:64],
        service_id=str(payload.get("serviceID") or "")[:64],
        payload=payload,
        fingerprint=digest,
        remote_ip=remote_ip or None,
    )


class WebhookService:
    def __init__(self, engine, catalog):
        self.engine = engine
        self.catalog = catalog

    def process(self, payload, event=None):
        from vtpass.models import WebhookEvent

        event_type = payload.get("type")
        signals.webhook_received.send(sender=self.__class__, event=event, payload=payload)
        try:
            if event_type == WebhookType.TRANSACTION_UPDATE:
                handled = self._transaction_update(payload)
            elif event_type == WebhookType.VARIATIONS_UPDATE:
                handled = self._variations_update(payload)
            else:
                handled = False
        except Exception as exc:
            logger.exception("Failed to process VTpass webhook")
            if event is not None:
                WebhookEvent.objects.filter(pk=event.pk).update(state=WebhookEvent.FAILED, error=str(exc)[:2000])
            raise
        if event is not None:
            WebhookEvent.objects.filter(pk=event.pk).update(
                state=WebhookEvent.PROCESSED if handled else WebhookEvent.IGNORED,
                processed_at=timezone.now(),
            )
        return handled

    def _transaction_update(self, payload):
        from vtpass.models import Transaction

        data = payload.get("data") or {}
        request_id = data.get("requestId")
        if not request_id:
            return False
        txn = Transaction.objects.filter(request_id=request_id).first()
        if txn is None:
            logger.info("Webhook for unknown request_id %s ignored", request_id)
            return False
        if vtpass_settings.WEBHOOK["VERIFY_WITH_REQUERY"]:
            self.engine.requery(txn)
        else:
            self.engine.apply_response(txn, VTpassResponse(raw=data))
        return True

    def _variations_update(self, payload):
        service_id = payload.get("serviceID")
        if not service_id:
            return False
        if vtpass_settings.WEBHOOK["VERIFY_WITH_REQUERY"]:
            self.catalog.sync_variations(service_id)
        else:
            content = (payload.get("data") or {}).get("content") or {}
            self.catalog.sync_variations(service_id, content=content)
        signals.variations_updated.send(
            sender=self.__class__, service_id=service_id, summary=payload.get("summary") or {}, payload=payload
        )
        return True
