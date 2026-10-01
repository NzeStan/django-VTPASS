"""
Wallet backends: how a purchase is paid for.

``VTPASS["WALLET_BACKEND"]`` options:

* ``None`` (default) – the package does not move customer money. Collect
  payment however you like (card, transfer, your own ledger) and call the
  purchase API afterwards.
* ``"vtpass.wallets.ModelWalletBackend"`` – built-in wallet (``Wallet`` /
  ``WalletEntry`` models). The customer is debited before VTpass is called,
  refunded automatically on failure/reversal and credited cashback on success.
* Your own class implementing :class:`BaseWalletBackend` (e.g. to plug into an
  existing ledger or core-banking system).

Every operation takes a unique ``reference``; replaying the same reference is
a no-op, which makes refunds and cashback exactly-once even when a webhook
and a requery race each other.
"""

from decimal import Decimal

from django.db import IntegrityError, transaction as db_transaction

from vtpass import signals
from vtpass.constants import WalletEntryKind
from vtpass.exceptions import InsufficientFunds, VTpassTransactionError, VTpassValidationError
from vtpass.settings import vtpass_settings
from vtpass.utils import quantize


class BaseWalletBackend:
    def balance(self, user) -> Decimal:
        raise NotImplementedError

    def debit(self, user, amount, *, reference, kind=WalletEntryKind.PURCHASE, description="",
              transaction=None, metadata=None):
        """Remove funds or raise :class:`InsufficientFunds`. Must be idempotent per ``reference``."""
        raise NotImplementedError

    def credit(self, user, amount, *, reference, kind=WalletEntryKind.FUNDING, description="",
               transaction=None, metadata=None):
        """Add funds. Must be idempotent per ``reference``."""
        raise NotImplementedError


class ModelWalletBackend(BaseWalletBackend):
    """Built-in wallet stored in the ``Wallet`` and ``WalletEntry`` tables."""

    def get_wallet(self, user, lock=False):
        from vtpass.models import Wallet

        if user is None or not getattr(user, "pk", None):
            raise VTpassValidationError("A saved user is required for wallet operations.")
        wallet, _ = Wallet.objects.get_or_create(user=user, defaults={"currency": vtpass_settings.CURRENCY})
        if lock:
            wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        return wallet

    def balance(self, user) -> Decimal:
        return self.get_wallet(user).balance

    def debit(self, user, amount, *, reference, kind=WalletEntryKind.PURCHASE, description="",
              transaction=None, metadata=None):
        return self._post(user, amount, "debit", reference, kind, description, transaction, metadata)

    def credit(self, user, amount, *, reference, kind=WalletEntryKind.FUNDING, description="",
               transaction=None, metadata=None):
        return self._post(user, amount, "credit", reference, kind, description, transaction, metadata)

    def _post(self, user, amount, direction, reference, kind, description, transaction, metadata):
        from vtpass.models import WalletEntry

        amount = quantize(amount)
        if amount <= 0:
            raise VTpassValidationError("Wallet amounts must be positive.")
        if not reference:
            raise VTpassValidationError("A unique reference is required.")

        with db_transaction.atomic():
            wallet = self.get_wallet(user, lock=True)
            existing = WalletEntry.objects.filter(reference=reference).first()
            if existing is not None:
                if existing.wallet_id != wallet.pk or existing.direction != direction or existing.amount != amount:
                    raise VTpassTransactionError(f"Wallet reference {reference!r} was already used differently.")
                return existing
            before = wallet.balance
            if direction == WalletEntry.DEBIT:
                if wallet.is_locked:
                    raise InsufficientFunds("This wallet is locked.")
                if before < amount:
                    raise InsufficientFunds(
                        f"Insufficient balance: {before} available, {amount} required.",
                        balance=before, required=amount,
                    )
                after = before - amount
            else:
                after = before + amount
            try:
                with db_transaction.atomic():
                    entry = WalletEntry.objects.create(
                        wallet=wallet, direction=direction, kind=kind, amount=amount,
                        balance_before=before, balance_after=after, reference=reference,
                        description=description[:255], transaction=transaction, metadata=metadata or {},
                    )
            except IntegrityError:
                # A concurrent request committed the same reference first.
                return WalletEntry.objects.get(reference=reference)
            wallet.balance = after
            wallet.save(update_fields=["balance", "updated_at"])

            signal = signals.wallet_debited if direction == WalletEntry.DEBIT else signals.wallet_credited
            db_transaction.on_commit(lambda: signal.send(sender=type(wallet), wallet=wallet, entry=entry))
        return entry


def get_wallet_backend():
    cls = vtpass_settings.import_from_setting("WALLET_BACKEND")
    return cls() if cls else None


# Convenience helpers for funding flows (e.g. call from your Paystack/Flutterwave webhook)
def fund_wallet(user, amount, reference, description="Wallet funding", metadata=None):
    backend = get_wallet_backend()
    if backend is None:
        raise VTpassTransactionError("No VTPASS['WALLET_BACKEND'] is configured.")
    return backend.credit(user, amount, reference=reference, kind=WalletEntryKind.FUNDING,
                          description=description, metadata=metadata)


def wallet_balance(user):
    backend = get_wallet_backend()
    if backend is None:
        raise VTpassTransactionError("No VTPASS['WALLET_BACKEND'] is configured.")
    return backend.balance(user)
