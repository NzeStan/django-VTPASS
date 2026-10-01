"""
Webhook endpoint for VTpass callbacks. Plain Django (no DRF needed).

Register ``https://<your-host>/<prefix>/webhook/<VTPASS["WEBHOOK"]["TOKEN"]>/``
as the callback URL in your VTpass dashboard.

Security:
* the secret token in the path is compared in constant time;
* optional source IP allowlist (``WEBHOOK["ALLOWED_IPS"]``);
* body size is capped and only JSON objects are accepted;
* the payload is never trusted for money movement – the transaction is
  re-queried from VTpass before it is settled (``VERIFY_WITH_REQUERY``);
* deliveries are deduplicated and processing is idempotent.
"""

import hmac
import json
import logging

from django.db import transaction as db_transaction
from django.http import Http404, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from vtpass.jobs import dispatch
from vtpass.services.webhooks import record_event
from vtpass.settings import vtpass_settings
from vtpass.utils import get_client_ip

logger = logging.getLogger("vtpass")
MAX_BODY_BYTES = 512 * 1024
ACK = {"response": "success"}


@csrf_exempt
@require_POST
def webhook(request, token=""):
    config = vtpass_settings.WEBHOOK
    expected = config.get("TOKEN") or ""
    if expected and not hmac.compare_digest(str(token).encode(), str(expected).encode()):
        raise Http404()

    remote_ip = get_client_ip(request, vtpass_settings.TRUSTED_IP_HEADER)
    allowed = config.get("ALLOWED_IPS") or []
    if allowed and remote_ip not in allowed:
        logger.warning("Rejected VTpass webhook from %s", remote_ip)
        return HttpResponseForbidden()

    if len(request.body) > MAX_BODY_BYTES:
        return HttpResponseBadRequest("Payload too large")
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid JSON")
    if not isinstance(payload, dict) or not payload.get("type"):
        return HttpResponseBadRequest("Invalid payload")

    event = record_event(payload, remote_ip=remote_ip or None)
    event_id = event.pk if event is not None else None

    def run():
        try:
            dispatch("process_webhook", payload, event_id)
        except Exception:
            # Already recorded; pending transactions are also settled by the requery job.
            logger.exception("VTpass webhook processing failed")

    db_transaction.on_commit(run)
    return JsonResponse(ACK)
