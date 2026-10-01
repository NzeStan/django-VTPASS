"""The purchase engine: money movement, status machine, requery, idempotency, limits and signals."""

from datetime import timedelta
from decimal import Decimal

import pytest
import requests
from django.test import override_settings
from django.utils import timezone

from tests.conftest import BASE, pay_body
from vtpass import signals
from vtpass.constants import Status
from vtpass.exceptions import InsufficientFunds, LimitExceeded, PurchaseDenied, VTpassValidationError
from vtpass.models import PricingRule, Service, ServiceCategory, Transaction, WalletEntry

pytestmark = pytest.mark.django_db


def balance(user):
    from vtpass.wallets import wallet_balance

    return wallet_balance(user)


class TestSuccessfulPurchase:
    def test_debits_wallet_and_records_transaction(self, api, vt, funded_user):
        api.post(BASE + "pay", json=pay_body(amount=100, total_amount=97, commission=3))
        txn = vt.airtime.buy("08031234567", 100, user=funded_user)
        assert txn.status == Status.SUCCESSFUL
        assert txn.service_id == "mtn" and txn.category == "airtime"
        assert txn.amount_charged == Decimal("100.00")
        assert txn.cost == Decimal("97.00") and txn.vtpass_commission == Decimal("3.00")
        assert txn.profit == Decimal("3.00")
        assert txn.completed_at is not None and txn.next_requery_at is None
        assert balance(funded_user) == Decimal("9900.00")

    def test_cashback_and_discount(self, api, vt, funded_user):
        PricingRule.objects.create(name="promo", category="airtime", discount_value=2, cashback_value=1)
        api.post(BASE + "pay", json=pay_body(amount=1000))
        txn = vt.airtime.buy("08031234567", 1000, user=funded_user)
        assert txn.amount_charged == Decimal("980.00")
        assert txn.cashback_paid and txn.cashback == Decimal("10.00")
        assert balance(funded_user) == Decimal("10000") - Decimal("980") + Decimal("10")
        kinds = set(WalletEntry.objects.filter(transaction=txn).values_list("kind", flat=True))
        assert kinds == {"purchase", "cashback"}

    def test_payload_sent_to_vtpass(self, api, vt, funded_user):
        import json

        api.post(BASE + "pay", json=pay_body())
        txn = vt.airtime.buy("+2348031234567", 100, user=funded_user)
        sent = json.loads(api.calls[0].request.body)
        assert sent == {"serviceID": "mtn", "amount": 100, "phone": "08031234567", "request_id": txn.request_id}

    def test_signals_fire_after_commit(self, api, vt, funded_user, django_capture_on_commit_callbacks):
        seen = []

        def record(name):
            def handler(sender, transaction, **kwargs):
                seen.append(name)
            return handler

        handlers = {
            signals.transaction_created: record("created"),
            signals.transaction_successful: record("successful"),
            signals.transaction_status_changed: record("changed"),
        }
        for signal, handler in handlers.items():
            signal.connect(handler)
        try:
            api.post(BASE + "pay", json=pay_body())
            with django_capture_on_commit_callbacks(execute=True):
                vt.airtime.buy("08031234567", 100, user=funded_user)
        finally:
            for signal, handler in handlers.items():
                signal.disconnect(handler)
        assert seen == ["created", "changed", "successful"]


class TestFailures:
    def test_failed_purchase_is_refunded(self, api, vt, funded_user):
        api.post(BASE + "pay", json={"code": "016", "response_description": "TRANSACTION FAILED"})
        txn = vt.airtime.buy("08031234567", 500, user=funded_user)
        assert txn.status == Status.FAILED
        assert txn.refunded and txn.refund_amount == Decimal("500.00")
        assert balance(funded_user) == Decimal("10000.00")
        assert txn.error_message == "TRANSACTION FAILED"

    def test_merchant_low_balance_fails_and_refunds(self, api, vt, funded_user):
        api.post(BASE + "pay", json={"code": "018", "response_description": "LOW WALLET BALANCE"})
        txn = vt.airtime.buy("08031234567", 500, user=funded_user)
        assert txn.status == Status.FAILED and txn.refunded
        assert balance(funded_user) == Decimal("10000.00")

    def test_insufficient_customer_funds_never_calls_vtpass(self, api, vt, user):
        with pytest.raises(InsufficientFunds):
            vt.airtime.buy("08031234567", 100, user=user)
        assert not Transaction.objects.exists()
        assert len(api.calls) == 0

    def test_auth_error_fails_cleanly(self, api, vt, funded_user):
        api.post(BASE + "pay", status=401, json={})
        txn = vt.airtime.buy("08031234567", 100, user=funded_user)
        assert txn.status == Status.FAILED and txn.refunded

    def test_refund_happens_once(self, vt, api, funded_user):
        api.post(BASE + "pay", json={"code": "016", "response_description": "TRANSACTION FAILED"})
        txn = vt.airtime.buy("08031234567", 500, user=funded_user)
        vt.engine.transition(txn, Status.FAILED)
        vt.engine.transition(txn, Status.REVERSED)
        assert WalletEntry.objects.filter(kind="refund").count() == 1
        assert balance(funded_user) == Decimal("10000.00")


class TestPendingAndRequery:
    def test_timeout_leaves_transaction_pending(self, api, vt, funded_user):
        api.post(BASE + "pay", body=requests.Timeout("slow"))
        txn = vt.airtime.buy("08031234567", 100, user=funded_user)
        assert txn.status == Status.PENDING
        assert not txn.refunded and txn.next_requery_at is not None
        assert balance(funded_user) == Decimal("9900.00")

    def test_processing_then_delivered(self, api, vt, funded_user):
        api.post(BASE + "pay", json={"code": "099", "response_description": "TRANSACTION IS PROCESSING"})
        txn = vt.airtime.buy("08031234567", 100, user=funded_user)
        assert txn.status == Status.PENDING
        api.post(BASE + "requery", json=pay_body())
        txn = vt.requery(txn)
        assert txn.status == Status.SUCCESSFUL and txn.requery_count == 1

    def test_unknown_request_id_fails_only_after_grace_period(self, api, vt, funded_user):
        api.post(BASE + "pay", body=requests.ConnectionError("down"))
        txn = vt.airtime.buy("08031234567", 100, user=funded_user)
        api.post(BASE + "requery", json={"code": "015", "response_description": "INVALID REQUEST ID"})
        txn = vt.requery(txn)
        assert txn.status == Status.PENDING
        Transaction.objects.filter(pk=txn.pk).update(created_at=timezone.now() - timedelta(minutes=30))
        txn.refresh_from_db()
        txn = vt.requery(txn)
        assert txn.status == Status.FAILED and txn.refunded
        assert balance(funded_user) == Decimal("10000.00")

    def test_requery_due_batch(self, api, vt, funded_user):
        api.post(BASE + "pay", json={"code": "099"})
        first = vt.airtime.buy("08031234567", 100, user=funded_user)
        second = vt.airtime.buy("08031234567", 200, user=funded_user)
        Transaction.objects.update(next_requery_at=timezone.now() - timedelta(seconds=1))
        api.post(BASE + "requery", json=pay_body())
        assert vt.requery_pending() == 2
        assert set(Transaction.objects.values_list("status", flat=True)) == {Status.SUCCESSFUL}
        assert first.pk != second.pk

    def test_requery_backoff_schedule(self, api, vt, funded_user):
        api.post(BASE + "pay", json={"code": "099"})
        txn = vt.airtime.buy("08031234567", 100, user=funded_user)
        api.post(BASE + "requery", json={"code": "099"})
        before = timezone.now()
        txn = vt.requery(txn)
        assert txn.next_requery_at >= before + timedelta(seconds=55)


class TestReversal:
    def test_reversal_after_success_refunds_net_of_cashback(self, api, vt, funded_user):
        PricingRule.objects.create(name="cb", cashback_value=5)
        api.post(BASE + "pay", json=pay_body(amount=1000))
        txn = vt.airtime.buy("08031234567", 1000, user=funded_user)
        assert balance(funded_user) == Decimal("9050.00")
        reversal = {"code": "040", "response_description": "TRANSACTION REVERSAL TO WALLET",
                    "content": {"transactions": {"status": "reversed"}}}
        api.post(BASE + "requery", json=reversal)
        txn = vt.requery(txn)
        assert txn.status == Status.REVERSED
        assert txn.refund_amount == Decimal("950.00")
        assert balance(funded_user) == Decimal("10000.00")

    def test_failed_cannot_become_successful(self, api, vt, funded_user):
        api.post(BASE + "pay", json={"code": "016"})
        txn = vt.airtime.buy("08031234567", 100, user=funded_user)
        api.post(BASE + "requery", json=pay_body())
        txn = vt.requery(txn)
        assert txn.status == Status.FAILED


class TestSafety:
    def test_idempotency_key_prevents_double_purchase(self, api, vt, funded_user):
        api.post(BASE + "pay", json=pay_body())
        first = vt.airtime.buy("08031234567", 100, user=funded_user, idempotency_key="tap-1")
        second = vt.airtime.buy("08031234567", 100, user=funded_user, idempotency_key="tap-1")
        assert first.pk == second.pk
        assert len(api.calls) == 1
        assert balance(funded_user) == Decimal("9900.00")

    def test_pre_purchase_veto(self, api, vt, funded_user):
        def require_pin(sender, metadata, **kwargs):
            if metadata.get("pin") != "1234":
                raise PurchaseDenied("Invalid transaction PIN.")

        signals.pre_purchase.connect(require_pin)
        try:
            with pytest.raises(PurchaseDenied):
                vt.airtime.buy("08031234567", 100, user=funded_user, metadata={"pin": "0000"})
            assert not Transaction.objects.exists()
            api.post(BASE + "pay", json=pay_body())
            assert vt.airtime.buy("08031234567", 100, user=funded_user, metadata={"pin": "1234"}).is_successful
        finally:
            signals.pre_purchase.disconnect(require_pin)

    def test_daily_limits(self, api, vt, funded_user, settings):
        settings.VTPASS = {**settings.VTPASS, "LIMITS": {"DAILY_AMOUNT_PER_USER": "300", "DAILY_COUNT_PER_USER": 5}}
        api.post(BASE + "pay", json=pay_body())
        vt.airtime.buy("08031234567", 200, user=funded_user)
        with pytest.raises(LimitExceeded):
            vt.airtime.buy("08031234567", 200, user=funded_user)

    def test_failed_transactions_do_not_count_towards_limits(self, api, vt, funded_user, settings):
        settings.VTPASS = {**settings.VTPASS, "LIMITS": {"DAILY_AMOUNT_PER_USER": "300"}}
        api.post(BASE + "pay", json={"code": "016"})
        vt.airtime.buy("08031234567", 200, user=funded_user)
        vt.airtime.buy("08031234567", 200, user=funded_user)

    def test_amount_limits_from_settings_and_catalogue(self, vt, funded_user, settings):
        settings.VTPASS = {**settings.VTPASS, "LIMITS": {"MIN_AMOUNT": "50", "MAX_AMOUNT": "50000"}}
        with pytest.raises(VTpassValidationError):
            vt.airtime.buy("08031234567", 10, user=funded_user)
        category = ServiceCategory.objects.create(identifier="airtime", name="Airtime")
        Service.objects.create(category=category, service_id="mtn", name="MTN", maximum_amount=1000)
        with pytest.raises(VTpassValidationError, match="maximum"):
            vt.airtime.buy("08031234567", 2000, user=funded_user)
        Service.objects.filter(service_id="mtn").update(is_active=False)
        with pytest.raises(VTpassValidationError, match="unavailable"):
            vt.airtime.buy("08031234567", 100, user=funded_user)

    def test_negative_or_missing_amount(self, vt, funded_user):
        with pytest.raises(VTpassValidationError):
            vt.airtime.buy("08031234567", -5, user=funded_user)
        with pytest.raises(VTpassValidationError):
            vt.purchase(service_id="mtn", phone="08031234567", user=funded_user)

    def test_wallet_required_for_anonymous(self, vt):
        with pytest.raises(VTpassValidationError):
            vt.airtime.buy("08031234567", 100)


class TestWithoutWallet:
    def test_external_payment_mode(self, api, funded_user, settings):
        from vtpass.services import VTpass

        settings.VTPASS = {**settings.VTPASS, "WALLET_BACKEND": None}
        api.post(BASE + "pay", json={"code": "016"})
        txn = VTpass().airtime.buy("08031234567", 100, user=funded_user)
        assert txn.status == Status.FAILED and not txn.wallet_charged and not txn.refunded
        assert balance_unchanged(funded_user)

    def test_charge_wallet_false(self, api, vt, funded_user):
        api.post(BASE + "pay", json=pay_body())
        txn = vt.airtime.buy("08031234567", 100, user=funded_user, charge_wallet=False)
        assert txn.is_successful and not txn.wallet_charged
        assert balance(funded_user) == Decimal("10000.00")

    def test_anonymous_purchase_without_wallet(self, api, vt):
        api.post(BASE + "pay", json=pay_body())
        txn = vt.airtime.buy("08031234567", 100, charge_wallet=False)
        assert txn.is_successful and txn.user is None


def balance_unchanged(user):
    from vtpass.wallets import ModelWalletBackend

    return ModelWalletBackend().balance(user) == Decimal("10000.00")


def test_beneficiary_saved(api, vt, funded_user):
    api.post(BASE + "pay", json=pay_body())
    vt.airtime.buy("08031234567", 100, user=funded_user, save_beneficiary=True)
    vt.airtime.buy("08031234567", 100, user=funded_user, save_beneficiary=True)
    beneficiary = funded_user.vtpass_beneficiaries.get()
    assert beneficiary.billers_code == "08031234567" and beneficiary.use_count == 2


@override_settings(VTPASS={"WALLET_BACKEND": None, "API_KEY": "k", "PUBLIC_KEY": "p", "SECRET_KEY": "s"})
def test_generic_purchase_for_new_service(api):
    import json

    from vtpass.services import VTpass

    api.post(BASE + "pay", json=pay_body())
    txn = VTpass().purchase(
        service_id="brand-new-service", phone="08031234567", amount=500, billers_code="ABC123",
        extra={"custom_field": "x"},
    )
    assert txn.is_successful
    assert json.loads(api.calls[0].request.body)["custom_field"] == "x"


class TestPriceTampering:
    def test_extra_cannot_override_core_fields(self, vt, funded_user):
        for key in ("variation_code", "amount", "billersCode", "serviceID", "quantity", "request_id"):
            with pytest.raises(VTpassValidationError):
                vt.purchase(service_id="mtn-data", phone="08031234567", amount=100, user=funded_user,
                            extra={key: "x"})
        assert not Transaction.objects.exists()

    def test_fixed_plan_without_price_is_refused(self, api, vt, funded_user):
        api.get(BASE + "service-variations", json={"content": {"variations": [
            {"variation_code": "mystery", "name": "?", "variation_amount": "0", "fixedPrice": "Yes"}]}})
        with pytest.raises(VTpassValidationError, match="unavailable"):
            vt.data.buy("08031234567", "mystery", amount=1, user=funded_user)
        assert len([c for c in api.calls if c.request.url.endswith("/pay")]) == 0

    def test_electricity_meter_type_is_sent_without_plan_pricing(self, api, vt, funded_user):
        import json

        api.post(BASE + "pay", json=pay_body())
        txn = vt.electricity.buy("ikedc", "1111111111111", "postpaid", 1500, "08031234567", user=funded_user)
        assert txn.variation_code == "postpaid" and txn.amount == Decimal("1500.00")
        assert json.loads(api.calls[0].request.body)["variation_code"] == "postpaid"
