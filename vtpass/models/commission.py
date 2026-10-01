"""
Pricing rules: how much *you* charge on top of (or below) the VTpass face value
and how much cashback you give back.

VTpass pays you a commission on every sale (a discount on what it debits from
your merchant wallet). A rule lets you decide what to do with that margin, the
way OPay/PalmPay do:

* ``fee``      – convenience fee added to what the customer pays (e.g. ₦100 on electricity).
* ``discount`` – instant discount: customer pays less than face value (e.g. 2% off airtime).
* ``cashback`` – credited to the customer's wallet after delivery (e.g. 3% back on data).

Each part can be a flat amount or a percentage of the face value, with caps
and floors. Rules can target a category, a service, a single plan, a user group
(agents/resellers get better rates) and an amount band, and can be time-boxed
for promos. The most specific active rule with the highest priority wins.
"""

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from vtpass.constants import AmountType
from vtpass.models.base import TimeStampedModel

MONEY = {"max_digits": 14, "decimal_places": 2}


class PricingRuleQuerySet(models.QuerySet):
    def live(self, now=None):
        now = now or timezone.now()
        return self.filter(is_active=True).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gt=now),
        )


class PricingRule(TimeStampedModel):
    name = models.CharField(_("name"), max_length=128)
    is_active = models.BooleanField(_("active"), default=True)
    priority = models.IntegerField(_("priority"), default=0, help_text=_("Higher wins when several rules match."))

    # --- targeting (blank = any) ----------------------------------------------------
    category = models.CharField(_("category"), max_length=64, blank=True)
    service_id = models.CharField(_("service ID"), max_length=64, blank=True)
    variation_code = models.CharField(_("variation code"), max_length=128, blank=True)
    user_group = models.ForeignKey(
        Group, null=True, blank=True, on_delete=models.CASCADE, related_name="vtpass_pricing_rules",
        verbose_name=_("user group"),
    )
    min_amount = models.DecimalField(_("minimum face value"), **MONEY, null=True, blank=True)
    max_amount = models.DecimalField(_("maximum face value"), **MONEY, null=True, blank=True)
    starts_at = models.DateTimeField(_("starts at"), null=True, blank=True)
    ends_at = models.DateTimeField(_("ends at"), null=True, blank=True)

    # --- convenience fee -------------------------------------------------------------
    fee_type = models.CharField(_("fee type"), max_length=8, choices=AmountType.choices, default=AmountType.FLAT)
    fee_value = models.DecimalField(_("fee value"), max_digits=10, decimal_places=2, default=0)
    fee_cap = models.DecimalField(_("fee cap"), **MONEY, null=True, blank=True)
    fee_min = models.DecimalField(_("minimum fee"), **MONEY, null=True, blank=True)

    # --- instant discount ------------------------------------------------------------
    discount_type = models.CharField(
        _("discount type"), max_length=8, choices=AmountType.choices, default=AmountType.PERCENT
    )
    discount_value = models.DecimalField(_("discount value"), max_digits=10, decimal_places=2, default=0)
    discount_cap = models.DecimalField(_("discount cap"), **MONEY, null=True, blank=True)

    # --- cashback ----------------------------------------------------------------------
    cashback_type = models.CharField(
        _("cashback type"), max_length=8, choices=AmountType.choices, default=AmountType.PERCENT
    )
    cashback_value = models.DecimalField(_("cashback value"), max_digits=10, decimal_places=2, default=0)
    cashback_cap = models.DecimalField(_("cashback cap"), **MONEY, null=True, blank=True)

    description = models.TextField(_("description"), blank=True)

    objects = PricingRuleQuerySet.as_manager()

    class Meta:
        verbose_name = _("pricing rule")
        verbose_name_plural = _("pricing rules")
        ordering = ("-priority", "name")

    def __str__(self):
        return self.name

    def clean(self):
        if self.min_amount is not None and self.max_amount is not None and self.min_amount > self.max_amount:
            raise ValidationError(_("Minimum face value cannot exceed maximum face value."))
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            raise ValidationError(_("The rule must start before it ends."))
        for prefix in ("fee", "discount", "cashback"):
            value = getattr(self, f"{prefix}_value")
            if value is not None and value < 0:
                raise ValidationError({f"{prefix}_value": _("Must not be negative.")})
            if getattr(self, f"{prefix}_type") == AmountType.PERCENT and value and value > 100:
                raise ValidationError({f"{prefix}_value": _("A percentage cannot exceed 100.")})

    @property
    def specificity(self):
        return sum(
            bool(value) for value in (self.category, self.service_id, self.variation_code, self.user_group_id)
        ) + int(self.min_amount is not None or self.max_amount is not None)

    def as_dict(self):
        return {
            "id": self.pk,
            "name": self.name,
            "fee_type": self.fee_type, "fee_value": self.fee_value, "fee_cap": self.fee_cap, "fee_min": self.fee_min,
            "discount_type": self.discount_type, "discount_value": self.discount_value,
            "discount_cap": self.discount_cap,
            "cashback_type": self.cashback_type, "cashback_value": self.cashback_value,
            "cashback_cap": self.cashback_cap,
        }
