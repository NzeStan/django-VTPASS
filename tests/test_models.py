"""Pricing rules and the built-in wallet ledger."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from vtpass.exceptions import InsufficientFunds, VTpassTransactionError, VTpassValidationError
from vtpass.models import PricingRule, Wallet, WalletEntry
from vtpass.pricing import FlatPricing, RuleBasedPricing

pytestmark = pytest.mark.django_db


def quote(**kwargs):
    defaults = {"face_value": Decimal("1000"), "service_id": "mtn", "category": "airtime", "variation_code": ""}
    defaults.update(kwargs)
    return RuleBasedPricing().quote(**defaults)


class TestPricing:
    def test_no_rule_means_face_value(self):
        q = quote()
        assert (q.fee, q.discount, q.cashback, q.amount_payable) == (0, 0, 0, Decimal("1000.00"))

    def test_fee_discount_and_cashback(self):
        PricingRule.objects.create(
            name="airtime", category="airtime", fee_type="flat", fee_value=10,
            discount_type="percent", discount_value=2, cashback_type="percent", cashback_value=1,
        )
        q = quote()
        assert q.fee == Decimal("10.00")
        assert q.discount == Decimal("20.00")
        assert q.cashback == Decimal("10.00")
        assert q.amount_payable == Decimal("990.00")
        assert q.rule["name"] == "airtime"

    def test_most_specific_rule_wins_then_priority(self):
        PricingRule.objects.create(name="any", discount_value=1)
        PricingRule.objects.create(name="category", category="airtime", discount_value=2)
        PricingRule.objects.create(name="service", category="airtime", service_id="mtn", discount_value=3)
        assert quote().rule["name"] == "service"
        PricingRule.objects.create(name="promo", discount_value=5, priority=10)
        assert quote().rule["name"] == "promo"

    def test_rule_scopes(self):
        PricingRule.objects.create(name="glo only", service_id="glo", discount_value=3)
        PricingRule.objects.create(name="big tickets", min_amount=5000, cashback_value=2)
        assert quote().rule is None
        assert quote(face_value=Decimal("6000")).rule["name"] == "big tickets"

    def test_time_window_and_inactive(self):
        now = timezone.now()
        PricingRule.objects.create(name="expired", discount_value=5, ends_at=now - timedelta(days=1))
        PricingRule.objects.create(name="future", discount_value=5, starts_at=now + timedelta(days=1))
        PricingRule.objects.create(name="off", discount_value=5, is_active=False)
        assert quote().rule is None

    def test_user_group_pricing_for_agents(self, user):
        agents = Group.objects.create(name="agents")
        PricingRule.objects.create(name="retail", discount_value=1)
        PricingRule.objects.create(name="agents", user_group=agents, discount_value=3)
        assert quote(user=user).rule["name"] == "retail"
        user.groups.add(agents)
        assert quote(user=user).rule["name"] == "agents"
        assert quote(user=user).discount == Decimal("30.00")

    def test_caps_and_discount_never_exceeds_face_value(self):
        PricingRule.objects.create(name="cap", discount_type="flat", discount_value=5000, cashback_value=10,
                                   cashback_cap=50)
        q = quote()
        assert q.discount == Decimal("1000.00") and q.amount_payable == Decimal("0.00")
        assert q.cashback == Decimal("50.00")

    def test_settings_rules_used_when_no_db_rule(self):
        rules = [{"name": "electricity fee", "category": "electricity-bill", "fee_type": "flat", "fee_value": "100"}]
        with override_settings(VTPASS={"PRICING_RULES": rules}):
            q = quote(category="electricity-bill", service_id="ikeja-electric")
        assert q.fee == Decimal("100.00") and q.amount_payable == Decimal("1100.00")

    def test_cashback_can_be_disabled(self):
        PricingRule.objects.create(name="cb", cashback_value=5)
        with override_settings(VTPASS={"CASHBACK_ENABLED": False}):
            assert quote().cashback == 0

    def test_flat_pricing(self):
        assert FlatPricing().quote(face_value=Decimal("50")).amount_payable == Decimal("50.00")

    def test_rule_validation(self):
        with pytest.raises(ValidationError):
            PricingRule(name="bad", discount_type="percent", discount_value=150).clean()
        with pytest.raises(ValidationError):
            PricingRule(name="bad", min_amount=10, max_amount=5).clean()


class TestWallet:
    def test_credit_and_debit(self, user, wallet_backend):
        wallet_backend.credit(user, Decimal("500"), reference="f1")
        entry = wallet_backend.debit(user, Decimal("200"), reference="d1")
        assert wallet_backend.balance(user) == Decimal("300.00")
        assert (entry.balance_before, entry.balance_after) == (Decimal("500.00"), Decimal("300.00"))

    def test_insufficient_funds(self, user, wallet_backend):
        wallet_backend.credit(user, Decimal("100"), reference="f1")
        with pytest.raises(InsufficientFunds):
            wallet_backend.debit(user, Decimal("100.01"), reference="d1")
        assert wallet_backend.balance(user) == Decimal("100.00")
        assert not WalletEntry.objects.filter(reference="d1").exists()

    def test_reference_is_idempotent(self, user, wallet_backend):
        first = wallet_backend.credit(user, Decimal("100"), reference="same")
        again = wallet_backend.credit(user, Decimal("100"), reference="same")
        assert first.pk == again.pk
        assert wallet_backend.balance(user) == Decimal("100.00")

    def test_reference_reuse_with_different_amount_rejected(self, user, wallet_backend):
        wallet_backend.credit(user, Decimal("100"), reference="same")
        with pytest.raises(VTpassTransactionError):
            wallet_backend.credit(user, Decimal("999"), reference="same")

    def test_locked_wallet_cannot_be_debited(self, user, wallet_backend):
        wallet_backend.credit(user, Decimal("100"), reference="f1")
        Wallet.objects.filter(user=user).update(is_locked=True)
        with pytest.raises(InsufficientFunds):
            wallet_backend.debit(user, Decimal("10"), reference="d1")

    def test_non_positive_amounts_rejected(self, user, wallet_backend):
        with pytest.raises(VTpassValidationError):
            wallet_backend.credit(user, Decimal("0"), reference="zero")

    def test_wallet_signals(self, user, wallet_backend, django_capture_on_commit_callbacks):
        from vtpass import signals

        seen = []
        handler = lambda sender, wallet, entry, **kw: seen.append(entry.reference)  # noqa: E731
        signals.wallet_credited.connect(handler)
        try:
            with django_capture_on_commit_callbacks(execute=True):
                wallet_backend.credit(user, Decimal("5"), reference="sig")
        finally:
            signals.wallet_credited.disconnect(handler)
        assert seen == ["sig"]

    def test_fund_wallet_helper(self, user):
        from vtpass.wallets import fund_wallet, wallet_balance

        fund_wallet(user, "2500", reference="paystack-ref-1")
        assert wallet_balance(user) == Decimal("2500.00")
