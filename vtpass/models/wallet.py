"""
Optional built-in customer wallet with an append-only ledger.

Only used when ``VTPASS["WALLET_BACKEND"] = "vtpass.wallets.ModelWalletBackend"``.
Balances are changed exclusively through :mod:`vtpass.wallets`, which locks
the wallet row (``SELECT ... FOR UPDATE``), records ``balance_before``/``after``
and enforces unique references, so concurrent purchases can never overdraw a
wallet or double-apply a refund.
"""

from decimal import Decimal

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from vtpass.constants import WalletEntryKind
from vtpass.models.base import TimeStampedModel, check_constraint

MONEY = {"max_digits": 14, "decimal_places": 2}


class Wallet(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="vtpass_wallet", verbose_name=_("user")
    )
    balance = models.DecimalField(_("balance"), **MONEY, default=Decimal("0"))
    currency = models.CharField(_("currency"), max_length=3, default="NGN")
    is_locked = models.BooleanField(_("locked"), default=False, help_text=_("Locked wallets cannot be debited."))

    class Meta:
        verbose_name = _("wallet")
        verbose_name_plural = _("wallets")
        constraints = [check_constraint(Q(balance__gte=0), "vtpass_wallet_non_negative_balance")]

    def __str__(self):
        return f"{self.user} - {self.currency} {self.balance}"


class WalletEntry(TimeStampedModel):
    CREDIT = "credit"
    DEBIT = "debit"
    DIRECTIONS = ((CREDIT, _("Credit")), (DEBIT, _("Debit")))

    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="entries", verbose_name=_("wallet"))
    direction = models.CharField(_("direction"), max_length=6, choices=DIRECTIONS)
    kind = models.CharField(_("kind"), max_length=16, choices=WalletEntryKind.choices)
    amount = models.DecimalField(_("amount"), **MONEY)
    balance_before = models.DecimalField(_("balance before"), **MONEY)
    balance_after = models.DecimalField(_("balance after"), **MONEY)
    reference = models.CharField(_("reference"), max_length=128, unique=True)
    description = models.CharField(_("description"), max_length=255, blank=True)
    transaction = models.ForeignKey(
        "vtpass.Transaction", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="wallet_entries", verbose_name=_("transaction"),
    )
    metadata = models.JSONField(_("metadata"), encoder=DjangoJSONEncoder, default=dict, blank=True)

    class Meta:
        verbose_name = _("wallet entry")
        verbose_name_plural = _("wallet entries")
        ordering = ("-created_at", "-id")
        constraints = [check_constraint(Q(amount__gt=0), "vtpass_wallet_entry_positive_amount")]

    def __str__(self):
        sign = "+" if self.direction == self.CREDIT else "-"
        return f"{sign}{self.amount} {self.kind} ({self.reference})"
