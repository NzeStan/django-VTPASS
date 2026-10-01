# Extending: signals, notifications, Celery and custom backends

## Signals

Everything outside the core money flow is a plugin built on `vtpass.signals`. Post-event signals are
sent **after the database commit**, so a slow or failing receiver can never roll back a purchase.

| Signal | kwargs | When |
|---|---|---|
| `pre_purchase` | `user, service_id, quote, payload, request, metadata` | Before any money moves. **Raise `PurchaseDenied` to block** |
| `transaction_created` | `transaction` | Row created (wallet already debited) |
| `transaction_status_changed` | `transaction, old_status, new_status` | Any status change |
| `transaction_pending` / `_successful` / `_failed` / `_reversed` | `transaction` | Specific outcomes |
| `transaction_refunded` | `transaction, amount` | Refund credited to wallet |
| `cashback_paid` | `transaction, amount` | Cashback credited |
| `wallet_credited` / `wallet_debited` | `wallet, entry` | Built-in wallet movements |
| `webhook_received` | `event, payload` | Any VTpass callback |
| `variations_updated` | `service_id, summary, payload` | VTpass changed a service's plans |
| `catalog_synced` | `categories, services, variations` | After a sync |
| `sms_sent` | `message, result` | After an SMS |
| `merchant_balance_low` | `balance, threshold` | Balance check below `LOW_BALANCE_THRESHOLD` |

### Transaction PIN / KYC

```python
from django.contrib.auth.hashers import check_password
from django.dispatch import receiver
from vtpass import signals
from vtpass.exceptions import PurchaseDenied

@receiver(signals.pre_purchase)
def require_pin(sender, user, request, metadata, quote, **kwargs):
    pin = (request.data.get("pin") if request is not None else None) or metadata.get("pin")
    if not check_password(pin or "", user.profile.transaction_pin):
        raise PurchaseDenied("Incorrect transaction PIN.")
    if user.profile.kyc_tier < 2 and quote.amount_payable > 50_000:
        raise PurchaseDenied("Upgrade your KYC tier to make purchases above ₦50,000.")
```

The REST API turns `PurchaseDenied` into HTTP 403.

### Referral bonus, loyalty points, push notifications

```python
@receiver(signals.transaction_successful)
def reward(sender, transaction, **kwargs):
    award_points.delay(transaction.user_id, transaction.amount)    # your own task
```

## Notifications

Built-in backends:

- `vtpass.notifications.backends.SMSBackend`: texts `transaction.phone` through VTpass Messaging.
- `vtpass.notifications.backends.EmailBackend`: emails `transaction.email` (or the user's email).
- `vtpass.notifications.backends.LoggingBackend`: writes to the log (development).

Custom backend (push, WhatsApp, in-app inbox...):

```python
from vtpass.notifications import render
from vtpass.notifications.backends import BaseNotificationBackend

class PushBackend(BaseNotificationBackend):
    channel = "sms"   # reuse the short SMS template text

    def send(self, event, transaction, context):
        if not transaction.user_id:
            return False
        send_push(transaction.user_id, render(self.template(event), context))
        return True
```

A failing backend is logged and skipped. It never affects the purchase or the other backends.

## Celery

Set `VTPASS["USE_CELERY"] = True`. Tasks (all named `vtpass.*`):

| Task | Purpose |
|---|---|
| `vtpass.requery_pending` | Settle due pending transactions (run every minute) |
| `vtpass.requery_transaction` | Requery one transaction |
| `vtpass.process_webhook` | Webhook processing (webhooks dispatch here automatically) |
| `vtpass.sync_catalog` / `vtpass.sync_variations` | Catalogue refresh |
| `vtpass.check_merchant_balance` | Low-balance alert |
| `vtpass.send_notification` / `vtpass.send_sms` | Messaging |

With Celery enabled the webhook view acknowledges VTpass immediately and processing runs on a
worker. Without it, processing (including the verification requery) runs inline before the
acknowledgement is returned. That's fine for small volumes; use Celery in production.

`vtpass.jobs.dispatch(name, *args)` runs any job inline or on Celery, so you can call jobs the same
way from your code.

## Custom pricing engine

```python
from vtpass.pricing import BasePricing, Quote

class MyPricing(BasePricing):
    def quote(self, *, face_value, service_id, category="", variation_code="", user=None, quantity=1):
        return Quote(face_value=face_value, fee=..., discount=..., cashback=...)

VTPASS = {"PRICING_BACKEND": "myapp.pricing.MyPricing"}
```

## Subclassing API views

Every view is a normal DRF `APIView`:

```python
from vtpass.api.views.airtime import AirtimePurchaseView

class MyAirtimeView(AirtimePurchaseView):
    permission_classes = [IsAuthenticated, HasVerifiedPhone]
```

## Multi-tenant (several VTpass accounts)

```python
from vtpass.client import VTpassClient
from vtpass.services import VTpass

vt = VTpass(client=VTpassClient(api_key=tenant.key, public_key=tenant.pk, secret_key=tenant.sk))
```

## Security notes

- Keep `WEBHOOK.VERIFY_WITH_REQUERY` on. VTpass callbacks are unsigned, and requery is the only
  trustworthy source of truth.
- Set a long random `WEBHOOK.TOKEN`. Add `ALLOWED_IPS` if VTpass gives you their egress IPs.
- `extra` fields can never override core purchase fields, and fixed-price plans are always priced
  from VTpass, never from client input.
- The REST API never shows merchant-side errors (your VTpass balance, IP whitelisting) to customers.
- Ledgers are read-only in the admin. Money only moves through the services layer.
