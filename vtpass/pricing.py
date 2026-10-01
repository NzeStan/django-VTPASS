"""
Pricing engine: turns a face value into what the customer pays and earns.

The default :class:`RuleBasedPricing` reads :class:`~vtpass.models.PricingRule`
rows from the database, then falls back to rules declared in settings:

    VTPASS = {
        "PRICING_RULES": [
            {"name": "Airtime 2% off", "category": "airtime",
             "discount_type": "percent", "discount_value": "2", "discount_cap": "500"},
            {"name": "Electricity fee", "category": "electricity-bill",
             "fee_type": "flat", "fee_value": "100"},
            {"name": "Data cashback", "category": "data",
             "cashback_type": "percent", "cashback_value": "3"},
        ],
    }

Swap the whole engine with ``VTPASS["PRICING_BACKEND"] = "myapp.pricing.MyPricing"``
(subclass :class:`BasePricing` and implement ``quote``).
"""

from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any, Dict, Optional

from vtpass.settings import vtpass_settings
from vtpass.utils import compute_amount, quantize, to_decimal

ZERO = Decimal("0.00")


@dataclass
class Quote:
    face_value: Decimal
    fee: Decimal = ZERO
    discount: Decimal = ZERO
    cashback: Decimal = ZERO
    rule: Optional[Dict[str, Any]] = None
    currency: str = "NGN"

    @property
    def amount_payable(self) -> Decimal:
        return quantize(max(self.face_value + self.fee - self.discount, ZERO))

    def as_dict(self):
        data = asdict(self)
        data["amount_payable"] = self.amount_payable
        return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in data.items()}


class BasePricing:
    def quote(self, *, face_value, service_id, category="", variation_code="", user=None, quantity=1) -> Quote:
        raise NotImplementedError


class FlatPricing(BasePricing):
    """No fees, discounts or cashback: the customer pays the face value."""

    def quote(self, *, face_value, **kwargs) -> Quote:
        return Quote(face_value=quantize(face_value), currency=vtpass_settings.CURRENCY)


class RuleBasedPricing(BasePricing):
    def quote(self, *, face_value, service_id, category="", variation_code="", user=None, quantity=1) -> Quote:
        face_value = quantize(face_value)
        rule = self.find_rule(
            face_value=face_value, service_id=service_id, category=category,
            variation_code=variation_code, user=user,
        )
        quote = Quote(face_value=face_value, currency=vtpass_settings.CURRENCY)
        if rule is None:
            return quote
        quote.fee = compute_amount(
            face_value, rule.get("fee_type", "flat"), rule.get("fee_value"),
            cap=rule.get("fee_cap"), minimum=rule.get("fee_min"),
        )
        quote.discount = min(
            compute_amount(face_value, rule.get("discount_type", "percent"), rule.get("discount_value"),
                           cap=rule.get("discount_cap")),
            face_value,
        )
        if vtpass_settings.CASHBACK_ENABLED:
            quote.cashback = compute_amount(
                face_value, rule.get("cashback_type", "percent"), rule.get("cashback_value"),
                cap=rule.get("cashback_cap"),
            )
        quote.rule = {k: (str(v) if isinstance(v, Decimal) else v) for k, v in rule.items()}
        return quote

    # ---- rule lookup -------------------------------------------------------------
    def find_rule(self, *, face_value, service_id, category, variation_code, user):
        rule = self._find_db_rule(face_value, service_id, category, variation_code, user)
        if rule is not None:
            return rule.as_dict()
        return self._find_settings_rule(face_value, service_id, category, variation_code)

    def _find_db_rule(self, face_value, service_id, category, variation_code, user):
        from django.db.models import Q

        from vtpass.models import PricingRule

        group_ids = []
        if user is not None and getattr(user, "is_authenticated", False):
            group_ids = list(user.groups.values_list("id", flat=True))
        rules = (
            PricingRule.objects.live()
            .filter(Q(category="") | Q(category=category or ""))
            .filter(Q(service_id="") | Q(service_id=service_id or ""))
            .filter(Q(variation_code="") | Q(variation_code=variation_code or ""))
            .filter(Q(user_group__isnull=True) | Q(user_group_id__in=group_ids))
            .filter(Q(min_amount__isnull=True) | Q(min_amount__lte=face_value))
            .filter(Q(max_amount__isnull=True) | Q(max_amount__gte=face_value))
        )
        candidates = list(rules[:50])
        if not candidates:
            return None
        return max(candidates, key=lambda r: (r.priority, r.specificity, r.pk))

    @staticmethod
    def _find_settings_rule(face_value, service_id, category, variation_code):
        best, best_key = None, None
        for index, rule in enumerate(vtpass_settings.as_dict().get("PRICING_RULES") or []):
            if not rule.get("is_active", True):
                continue
            checks = (("category", category), ("service_id", service_id), ("variation_code", variation_code))
            if any(rule.get(key) and rule.get(key) != value for key, value in checks):
                continue
            low, high = to_decimal(rule.get("min_amount")), to_decimal(rule.get("max_amount"))
            if (low is not None and face_value < low) or (high is not None and face_value > high):
                continue
            specificity = sum(bool(rule.get(key)) for key, _ in checks) + int(low is not None or high is not None)
            key = (int(rule.get("priority", 0)), specificity, -index)
            if best_key is None or key > best_key:
                best, best_key = rule, key
        return dict(best) if best else None


def get_pricing_backend() -> BasePricing:
    cls = vtpass_settings.import_from_setting("PRICING_BACKEND") or FlatPricing
    return cls()
