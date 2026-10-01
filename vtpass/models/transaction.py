"""The transaction ledger: one row per purchase sent (or about to be sent) to VTpass."""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from vtpass.constants import Status
from vtpass.models.base import TimeStampedModel, check_constraint

MONEY = {"max_digits": 14, "decimal_places": 2}


class TransactionQuerySet(models.QuerySet):
    def for_user(self, user):
        return self.filter(user=user)

    def open(self):
        return self.filter(status__in=Status.open())

    def successful(self):
        return self.filter(status=Status.SUCCESSFUL)

    def due_for_requery(self, now=None):
        now = now or timezone.now()
        return self.open().filter(Q(next_requery_at__isnull=True) | Q(next_requery_at__lte=now))

    def counting_towards_limits(self):
        return self.exclude(status__in=(Status.FAILED, Status.REVERSED))

    def today(self):
        start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(created_at__gte=start)

    def totals(self):
        return self.aggregate(
            face_value=Sum("amount"),
            charged=Sum("amount_charged"),
            cost=Sum("cost"),
            fees=Sum("fee"),
            discounts=Sum("discount"),
            cashback=Sum("cashback"),
            vtpass_commission=Sum("vtpass_commission"),
        )


class Transaction(TimeStampedModel):
    # --- who --------------------------------------------------------------------
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="vtpass_transactions", verbose_name=_("user"),
    )
    # --- identifiers ----------------------------------------------------------------
    request_id = models.CharField(_("VTpass request ID"), max_length=64, unique=True)
    idempotency_key = models.CharField(_("idempotency key"), max_length=128, null=True, blank=True)
    vtpass_transaction_id = models.CharField(_("VTpass transaction ID"), max_length=64, blank=True, db_index=True)
    # --- what ---------------------------------------------------------------------
    category = models.CharField(_("category"), max_length=64, blank=True, db_index=True)
    service_id = models.CharField(_("service ID"), max_length=64, db_index=True)
    variation_code = models.CharField(_("variation code"), max_length=128, blank=True)
    product_name = models.CharField(_("product name"), max_length=255, blank=True)
    billers_code = models.CharField(_("billers code"), max_length=128, blank=True, db_index=True,
                                    help_text=_("Phone, meter, smartcard, profile ID... being paid for."))
    phone = models.CharField(_("phone"), max_length=32, blank=True)
    email = models.EmailField(_("email"), blank=True)
    quantity = models.PositiveIntegerField(_("quantity"), default=1)
    # --- money ------------------------------------------------------------------------
    amount = models.DecimalField(_("face value"), **MONEY, help_text=_("Value sent to VTpass."))
    fee = models.DecimalField(_("convenience fee"), **MONEY, default=Decimal("0"))
    discount = models.DecimalField(_("discount"), **MONEY, default=Decimal("0"))
    amount_charged = models.DecimalField(_("amount charged"), **MONEY,
                                         help_text=_("What the customer paid: face value + fee - discount."))
    cashback = models.DecimalField(_("cashback"), **MONEY, default=Decimal("0"))
    cashback_paid = models.BooleanField(_("cashback paid"), default=False)
    cost = models.DecimalField(_("cost"), **MONEY, null=True, blank=True,
                               help_text=_("What VTpass debited from the merchant wallet (total_amount)."))
    vtpass_commission = models.DecimalField(_("VTpass commission"), **MONEY, null=True, blank=True)
    vtpass_commission_details = models.JSONField(
        _("VTpass commission details"), default=dict, blank=True, encoder=DjangoJSONEncoder
    )
    pricing = models.JSONField(_("pricing snapshot"), default=dict, blank=True, encoder=DjangoJSONEncoder)
    currency = models.CharField(_("currency"), max_length=3, default="NGN")
    # --- wallet bookkeeping -------------------------------------------------------------
    wallet_charged = models.BooleanField(_("wallet charged"), default=False)
    refunded = models.BooleanField(_("refunded"), default=False)
    refund_amount = models.DecimalField(_("refund amount"), **MONEY, default=Decimal("0"))
    # --- outcome --------------------------------------------------------------------
    status = models.CharField(_("status"), max_length=16, choices=Status.choices,
                              default=Status.INITIATED, db_index=True)
    response_code = models.CharField(_("response code"), max_length=8, blank=True)
    response_description = models.CharField(_("response description"), max_length=255, blank=True)
    error_message = models.TextField(_("error message"), blank=True)
    purchased_code = models.TextField(_("purchased code"), blank=True,
                                      help_text=_("Token, PIN or voucher text returned by VTpass."))
    vend_details = models.JSONField(_("vend details"), default=dict, blank=True, encoder=DjangoJSONEncoder)
    payload = models.JSONField(_("request payload"), default=dict, blank=True, encoder=DjangoJSONEncoder)
    response = models.JSONField(_("last response"), default=dict, blank=True, encoder=DjangoJSONEncoder)
    # --- context --------------------------------------------------------------------
    channel = models.CharField(_("channel"), max_length=32, blank=True)
    client_ip = models.GenericIPAddressField(_("client IP"), null=True, blank=True)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True, encoder=DjangoJSONEncoder)
    # --- requery bookkeeping -----------------------------------------------------------
    requery_count = models.PositiveIntegerField(_("requery count"), default=0)
    last_requeried_at = models.DateTimeField(_("last requeried at"), null=True, blank=True)
    next_requery_at = models.DateTimeField(_("next requery at"), null=True, blank=True)
    completed_at = models.DateTimeField(_("completed at"), null=True, blank=True)

    objects = TransactionQuerySet.as_manager()

    class Meta:
        verbose_name = _("transaction")
        verbose_name_plural = _("transactions")
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "next_requery_at"), name="vtpass_txn_requery_idx"),
            models.Index(fields=("user", "-created_at"), name="vtpass_txn_user_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("user", "idempotency_key"),
                condition=Q(idempotency_key__isnull=False),
                name="vtpass_unique_idempotency_key",
            ),
            check_constraint(
                Q(amount__gte=0) & Q(amount_charged__gte=0), "vtpass_txn_non_negative_amounts"
            ),
        ]
        permissions = [
            ("requery_transaction", "Can requery transactions"),
            ("send_sms", "Can send SMS through VTpass messaging"),
            ("view_merchant_balance", "Can view the VTpass merchant balance"),
        ]

    def __str__(self):
        return f"{self.service_id} {self.billers_code or self.phone} {self.amount} [{self.status}]"

    @property
    def reference(self):
        return self.request_id

    @property
    def is_open(self):
        return self.status in Status.open()

    @property
    def is_successful(self):
        return self.status == Status.SUCCESSFUL

    @property
    def profit(self):
        """Merchant margin: what the customer paid minus VTpass cost and cashback given."""
        if self.cost is None or self.status != Status.SUCCESSFUL:
            return None
        return self.amount_charged - self.cost - (self.cashback if self.cashback_paid else Decimal("0"))

    @property
    def token(self):
        return self.vend_details.get("token") or self.vend_details.get("mainToken") or None

    def schedule_next_requery(self, schedule, now=None):
        now = now or timezone.now()
        index = min(self.requery_count, len(schedule) - 1) if schedule else 0
        delay = schedule[index] if schedule else 300
        self.next_requery_at = now + timedelta(seconds=delay)
