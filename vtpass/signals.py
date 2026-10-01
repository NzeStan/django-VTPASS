"""
Signals: the extension points of django-vtpass.

Everything that is not "talk to VTpass and keep the books straight" is meant to
be plugged in through these signals: notifications, referral bonuses, loyalty
points, analytics, fraud checks, push messages, accounting exports...

All post-event signals are sent with ``transaction.on_commit`` so receivers
only ever see committed data, and a failing receiver can never roll back a
purchase. ``pre_purchase`` is the exception: it runs before money moves and a
receiver may raise :class:`vtpass.exceptions.PurchaseDenied` to block the
purchase (transaction PIN, KYC tier, velocity rules...).

    from django.dispatch import receiver
    from vtpass import signals

    @receiver(signals.transaction_successful)
    def give_points(sender, transaction, **kwargs):
        ...
"""

from django.dispatch import Signal

# Purchases ---------------------------------------------------------------------
#: kwargs: user, service_id, quote, payload, request, metadata. Raise PurchaseDenied to block.
pre_purchase = Signal()
#: kwargs: transaction
transaction_created = Signal()
#: kwargs: transaction, old_status, new_status
transaction_status_changed = Signal()
#: kwargs: transaction
transaction_pending = Signal()
#: kwargs: transaction
transaction_successful = Signal()
#: kwargs: transaction
transaction_failed = Signal()
#: kwargs: transaction
transaction_reversed = Signal()
#: kwargs: transaction, amount
transaction_refunded = Signal()
#: kwargs: transaction, amount
cashback_paid = Signal()

# Wallet ----------------------------------------------------------------------------
#: kwargs: wallet, entry
wallet_credited = Signal()
#: kwargs: wallet, entry
wallet_debited = Signal()

# Webhooks and catalogue -------------------------------------------------------------
#: kwargs: event (WebhookEvent or None), payload
webhook_received = Signal()
#: kwargs: service_id, summary, payload
variations_updated = Signal()
#: kwargs: categories, services, variations (counts)
catalog_synced = Signal()

# Messaging & merchant ---------------------------------------------------------------
#: kwargs: message (SMSMessage or None), result (SMSResult)
sms_sent = Signal()
#: kwargs: balance, threshold
merchant_balance_low = Signal()

STATUS_SIGNALS = {
    "pending": transaction_pending,
    "successful": transaction_successful,
    "failed": transaction_failed,
    "reversed": transaction_reversed,
}
