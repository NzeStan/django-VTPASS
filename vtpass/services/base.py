"""
Purchase engine: the one place where money moves.

Flow of :meth:`PurchaseEngine.purchase`:

1. resolve the face value (from the plan price when a variation is used);
2. validate amounts and limits, price the sale (fee / discount / cashback);
3. ``pre_purchase`` signal – receivers may veto (PIN, KYC, fraud rules);
4. in one DB transaction: create the ``Transaction`` row and debit the
   customer wallet (row locked, so concurrent purchases cannot overdraw);
5. call VTpass **outside** the DB transaction (no locks held during I/O);
6. apply the result through :meth:`PurchaseEngine.transition`, the state
   machine that refunds failures/reversals and pays cashback exactly once.

Anything ambiguous (timeouts, 5xx, "processing") leaves the transaction
PENDING. It is then settled by requery (Celery beat task, management command
or the webhook) – a purchase is never refunded unless VTpass says it failed.
"""

import logging
from decimal import Decimal

from django.core.cache import cache
from django.db import IntegrityError, transaction as db_transaction
from django.db.models import Count, F, Sum
from django.utils import timezone

from vtpass import signals
from vtpass.client import VTpassClient, VTpassResponse
from vtpass.constants import (
    SERVICE_CATEGORY_HINTS,
    STATUS_TRANSITIONS,
    ResponseCode,
    Status,
    WalletEntryKind,
)
from vtpass.exceptions import (
    DuplicateTransaction,
    LimitExceeded,
    VTpassAPIError,
    VTpassAuthenticationError,
    VTpassConfigError,
    VTpassError,
    VTpassNetworkError,
    VTpassValidationError,
)
from vtpass.pricing import get_pricing_backend
from vtpass.settings import vtpass_settings
from vtpass.utils import generate_request_id, get_client_ip, normalize_phone, quantize, to_decimal
from vtpass.wallets import get_wallet_backend

logger = logging.getLogger("vtpass")

# Fields the engine controls. ``extra`` may never override them, otherwise a
# caller could be charged for one plan while VTpass vends another.
PROTECTED_FIELDS = frozenset({
    "request_id", "serviceID", "amount", "phone", "billersCode", "variation_code",
    "quantity", "subscription_type", "email",
})


class PurchaseEngine:
    def __init__(self, client=None, wallet_backend=None, pricing=None):
        self._client = client
        self._wallet_backend = wallet_backend
        self._pricing = pricing

    # ---- collaborators (lazy so settings overrides are honoured) ----------------
    @property
    def client(self) -> VTpassClient:
        if self._client is None:
            self._client = VTpassClient()
        return self._client

    @property
    def wallet_backend(self):
        return self._wallet_backend if self._wallet_backend is not None else get_wallet_backend()

    @property
    def pricing(self):
        return self._pricing or get_pricing_backend()

    # ---- catalogue helpers -----------------------------------------------------
    def get_variations(self, service_id, use_cache=True, **params):
        """Plans for a service: local catalogue when synced, else the API (cached)."""
        from vtpass.models import Service

        if not params:
            service = Service.objects.filter(service_id=service_id, variations_synced_at__isnull=False).first()
            if service is not None:
                return [
                    {
                        "variation_code": v.variation_code,
                        "name": v.name,
                        "variation_amount": str(v.amount) if v.amount is not None else None,
                        "fixedPrice": "Yes" if v.fixed_price else "No",
                        **({"extra": v.extra} if v.extra else {}),
                    }
                    for v in service.variations.filter(is_active=True)
                ]
        key = "vtpass:variations:%s:%s" % (service_id, "&".join(f"{k}={v}" for k, v in sorted(params.items())))
        if use_cache:
            cached = cache.get(key)
            if cached is not None:
                return cached
        variations = self.client.get_variations(service_id, **params).get("variations", [])
        cache.set(key, variations, vtpass_settings.CATALOG_CACHE_TIMEOUT)
        return variations

    def find_variation(self, service_id, variation_code, **params):
        for variation in self.get_variations(service_id, **params):
            if str(variation.get("variation_code")) == str(variation_code):
                return variation
        # The cache may be stale (plans change often): retry once from the API.
        for variation in self.get_variations(service_id, use_cache=False, **params):
            if str(variation.get("variation_code")) == str(variation_code):
                return variation
        return None

    def category_for(self, service_id):
        from vtpass.models import Service

        service = Service.objects.select_related("category").filter(service_id=service_id).first()
        if service is not None:
            return service.category.identifier
        return str(SERVICE_CATEGORY_HINTS.get(service_id, ""))

    def verify(self, service_id, billers_code, type=None, **extra):
        return self.client.verify(service_id, billers_code, type=type, **extra)

    # ---- purchase ----------------------------------------------------------------
    def purchase(
        self,
        *,
        service_id,
        phone,
        amount=None,
        billers_code=None,
        variation_code=None,
        quantity=None,
        subscription_type=None,
        email=None,
        user=None,
        idempotency_key=None,
        charge_wallet=True,
        metadata=None,
        channel="",
        request=None,
        product_name="",
        save_beneficiary=False,
        variation_params=None,
        extra=None,
        lookup_variation=True,
    ):
        """
        Buy any VTpass product and return the :class:`~vtpass.models.Transaction`.

        ``extra`` carries additional VTpass fields verbatim (insurance details,
        ``operator_id``, ``country_code``...). ``variation_params`` are passed to
        the variations lookup (international airtime). Check ``transaction.status``
        afterwards: successful, pending (will settle by requery/webhook) or failed.

        ``lookup_variation=False`` sends ``variation_code`` as-is without pricing
        from a plan (electricity uses it for the meter type); the amount is then
        always the one passed in.
        """
        from vtpass.models import Transaction

        if not service_id:
            raise VTpassValidationError("service_id is required.", errors={"service_id": ["Required."]})
        phone = normalize_phone(phone)
        if not phone:
            raise VTpassValidationError("A phone number is required.", errors={"phone": ["Required."]})
        clashing = PROTECTED_FIELDS.intersection(extra or {})
        if clashing:
            raise VTpassValidationError(
                "These fields cannot be passed in extra: " + ", ".join(sorted(clashing)),
                errors={"extra": ["Invalid keys."]},
            )
        user = user if (user is not None and getattr(user, "is_authenticated", False)) else None
        quantity = int(quantity) if quantity not in (None, "") else None
        if quantity is not None and quantity < 1:
            raise VTpassValidationError("Quantity must be at least 1.", errors={"quantity": ["Invalid."]})

        # Idempotency: replaying the same key returns the original transaction.
        if idempotency_key and user is not None:
            existing = Transaction.objects.filter(user=user, idempotency_key=idempotency_key).first()
            if existing is not None:
                return existing

        unit_amount, variation = self._resolve_amount(
            service_id, amount, variation_code if lookup_variation else None, variation_params or {}
        )
        face_value = quantize(unit_amount * (quantity or 1))
        self._check_amount_limits(service_id, face_value)

        category = self.category_for(service_id)
        quote = self.pricing.quote(
            face_value=face_value, service_id=service_id, category=category,
            variation_code=variation_code or "", user=user, quantity=quantity or 1,
        )
        payload = {
            "serviceID": service_id,
            "amount": unit_amount,
            "phone": phone,
            "billersCode": billers_code,
            "variation_code": variation_code,
            "quantity": quantity,
            "subscription_type": subscription_type,
            "email": email,
        }
        payload.update(extra or {})
        payload = {k: v for k, v in payload.items() if v not in (None, "")}

        signals.pre_purchase.send(
            sender=self.__class__, user=user, service_id=service_id, quote=quote,
            payload=payload, request=request, metadata=metadata or {},
        )

        backend = self.wallet_backend if charge_wallet else None
        if backend is not None and user is None:
            raise VTpassValidationError("An authenticated user is required to pay from a wallet.")

        request_id = generate_request_id()
        try:
            with db_transaction.atomic():
                if backend is not None and hasattr(backend, "get_wallet"):
                    # Serialise this user's purchases so limit checks and the debit see the same state.
                    backend.get_wallet(user, lock=True)
                self._check_user_limits(user, quote.amount_payable)
                txn = Transaction.objects.create(
                    user=user,
                    request_id=request_id,
                    idempotency_key=idempotency_key or None,
                    category=category,
                    service_id=service_id,
                    variation_code=variation_code or "",
                    product_name=product_name or (variation or {}).get("name", "")[:255],
                    billers_code=str(billers_code or ""),
                    phone=phone,
                    email=email or "",
                    quantity=quantity or 1,
                    amount=face_value,
                    fee=quote.fee,
                    discount=quote.discount,
                    amount_charged=quote.amount_payable,
                    cashback=quote.cashback,
                    pricing=quote.as_dict(),
                    currency=quote.currency,
                    payload=payload,
                    channel=channel or "",
                    client_ip=get_client_ip(request, vtpass_settings.TRUSTED_IP_HEADER) if request else None,
                    metadata=metadata or {},
                    status=Status.INITIATED,
                )
                if backend is not None and quote.amount_payable > 0:
                    backend.debit(
                        user, quote.amount_payable, reference=f"vtpass:debit:{request_id}",
                        kind=WalletEntryKind.PURCHASE, description=self._describe(txn), transaction=txn,
                    )
                    txn.wallet_charged = True
                    txn.save(update_fields=["wallet_charged", "updated_at"])
                db_transaction.on_commit(
                    lambda: signals.transaction_created.send(sender=Transaction, transaction=txn)
                )
        except IntegrityError:
            if idempotency_key and user is not None:
                existing = Transaction.objects.filter(user=user, idempotency_key=idempotency_key).first()
                if existing is not None:
                    return existing
                raise DuplicateTransaction()
            raise

        self._send_to_vtpass(txn, payload)
        txn.refresh_from_db()

        if save_beneficiary and user is not None and vtpass_settings.BENEFICIARIES_ENABLED:
            self._save_beneficiary(txn)
        return txn

    def _send_to_vtpass(self, txn, payload):
        try:
            response = self.client.pay(request_id=txn.request_id, **payload)
        except (VTpassConfigError, VTpassAuthenticationError) as exc:
            # Rejected before processing: nothing was vended.
            logger.error("VTpass purchase %s rejected: %s", txn.request_id, exc)
            self.transition(txn, Status.FAILED, error=str(exc), code=getattr(exc, "code", None) or "")
        except (VTpassNetworkError, VTpassAPIError) as exc:
            # Unknown outcome: keep it pending and let requery decide.
            logger.warning("VTpass purchase %s outcome unknown: %s", txn.request_id, exc)
            self.transition(txn, Status.PENDING, error=str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error while purchasing %s", txn.request_id)
            self.transition(txn, Status.PENDING, error=f"Unexpected error: {exc}")
        else:
            self.apply_response(txn, response)

    # ---- amount & limits -----------------------------------------------------------
    def _resolve_amount(self, service_id, amount, variation_code, variation_params):
        variation = None
        if variation_code:
            variation = self.find_variation(service_id, variation_code, **variation_params)
            if variation is None:
                raise VTpassValidationError(
                    f"Unknown plan {variation_code!r} for {service_id}.",
                    errors={"variation_code": ["Invalid plan."]},
                )
            fixed = str(variation.get("fixedPrice", "Yes")).lower() in ("yes", "true", "1")
            plan_amount = to_decimal(variation.get("variation_amount"))
            if fixed:
                if not plan_amount or plan_amount <= 0:
                    # Never let the caller pick the price of a fixed-price plan.
                    raise VTpassValidationError(
                        "The price of this plan is unavailable; please try again later.",
                        errors={"variation_code": ["Price unavailable."]},
                    )
                return plan_amount, variation
        value = to_decimal(amount)
        if value is None or value <= 0:
            raise VTpassValidationError("A positive amount is required.", errors={"amount": ["Invalid amount."]})
        return quantize(value), variation

    def _check_amount_limits(self, service_id, face_value):
        from vtpass.models import Service

        limits = vtpass_settings.LIMITS
        low, high = to_decimal(limits.get("MIN_AMOUNT")), to_decimal(limits.get("MAX_AMOUNT"))
        service = Service.objects.filter(service_id=service_id).only(
            "minimum_amount", "maximum_amount", "is_active"
        ).first()
        if service is not None:
            if not service.is_active:
                raise VTpassValidationError("This service is currently unavailable.")
            if service.minimum_amount and (low is None or service.minimum_amount > low):
                low = service.minimum_amount
            if service.maximum_amount and (high is None or service.maximum_amount < high):
                high = service.maximum_amount
        if low is not None and face_value < low:
            raise VTpassValidationError(f"The minimum amount is {low}.", errors={"amount": [f"Minimum is {low}."]})
        if high is not None and face_value > high:
            raise VTpassValidationError(f"The maximum amount is {high}.", errors={"amount": [f"Maximum is {high}."]})

    def _check_user_limits(self, user, amount_payable):
        from vtpass.models import Transaction

        limits = vtpass_settings.LIMITS
        max_amount = to_decimal(limits.get("DAILY_AMOUNT_PER_USER"))
        max_count = limits.get("DAILY_COUNT_PER_USER")
        if user is None or (max_amount is None and not max_count):
            return
        totals = Transaction.objects.for_user(user).today().counting_towards_limits().aggregate(
            total=Sum("amount_charged"), count=Count("id")
        )
        if max_amount is not None and (totals["total"] or Decimal("0")) + amount_payable > max_amount:
            raise LimitExceeded("Daily transaction amount limit reached.")
        if max_count and (totals["count"] or 0) + 1 > int(max_count):
            raise LimitExceeded("Daily transaction count limit reached.")

    # ---- state machine -------------------------------------------------------------
    def apply_response(self, txn, response: VTpassResponse):
        status = response.status
        error = ""
        if status == Status.FAILED:
            error = response.error_message or ResponseCode.DESCRIPTIONS.get(response.code, "Transaction failed")
        return self.transition(txn, status, response=response, error=error)

    def transition(self, txn, new_status, response: VTpassResponse = None, error="", code=""):
        """
        Move a transaction to ``new_status`` with row locking. Refunds,
        cashback and signals happen exactly once per transition. Illegal moves
        (e.g. failed -> successful) are ignored and logged.
        """
        from vtpass.models import Transaction

        with db_transaction.atomic():
            txn = Transaction.objects.select_for_update().get(pk=txn.pk)
            old_status = txn.status
            fields = {"updated_at"}

            if response is not None:
                self._store_response(txn, response, fields)
            elif code:
                txn.response_code = code
                fields.add("response_code")
            if error:
                txn.error_message = str(error)[:2000]
                fields.add("error_message")

            changed = new_status != old_status
            if changed and new_status not in STATUS_TRANSITIONS.get(old_status, set()):
                logger.warning(
                    "Ignoring illegal status change %s -> %s for %s", old_status, new_status, txn.request_id
                )
                txn.save(update_fields=list(fields))
                return txn

            if new_status == Status.PENDING:
                txn.schedule_next_requery(vtpass_settings.REQUERY["SCHEDULE"])
                fields.add("next_requery_at")
            if changed:
                txn.status = new_status
                fields.add("status")
                if new_status in Status.terminal():
                    txn.completed_at = timezone.now()
                    txn.next_requery_at = None
                    fields.update({"completed_at", "next_requery_at"})

            refund_amount = cashback_amount = None
            if changed and new_status == Status.SUCCESSFUL:
                cashback_amount = self._pay_cashback(txn, fields)
            if changed and new_status in (Status.FAILED, Status.REVERSED):
                refund_amount = self._refund(txn, fields)

            txn.save(update_fields=list(fields))

            if changed:
                self._emit(txn, old_status, new_status, refund_amount, cashback_amount)
        return txn

    def _store_response(self, txn, response, fields):
        txn.response_code = response.code[:8]
        txn.response_description = response.description[:255]
        fields.update({"response_code", "response_description"})
        if vtpass_settings.STORE_RAW_RESPONSES:
            txn.response = response.raw
            fields.add("response")
        if response.vtpass_transaction_id:
            txn.vtpass_transaction_id = response.vtpass_transaction_id
            fields.add("vtpass_transaction_id")
        info = response.transaction
        if info.get("product_name") and not txn.product_name:
            txn.product_name = str(info["product_name"])[:255]
            fields.add("product_name")
        if response.total_amount is not None:
            txn.cost = quantize(response.total_amount)
            fields.add("cost")
        if response.commission is not None:
            txn.vtpass_commission = quantize(response.commission)
            fields.add("vtpass_commission")
        if response.commission_details:
            txn.vtpass_commission_details = response.commission_details
            fields.add("vtpass_commission_details")
        if response.purchased_code:
            txn.purchased_code = response.purchased_code
            fields.add("purchased_code")
        details = response.vend_details
        if details:
            if response.token and "token" not in details:
                details["token"] = response.token
            txn.vend_details = {**txn.vend_details, **details}
            fields.add("vend_details")

    def _pay_cashback(self, txn, fields):
        backend = self.wallet_backend
        if (
            backend is None or txn.user is None or txn.cashback_paid or txn.cashback <= 0
            or not vtpass_settings.CASHBACK_ENABLED
        ):
            return None
        backend.credit(
            txn.user, txn.cashback, reference=f"vtpass:cashback:{txn.request_id}",
            kind=WalletEntryKind.CASHBACK, description=f"Cashback on {self._describe(txn)}", transaction=txn,
        )
        txn.cashback_paid = True
        fields.add("cashback_paid")
        return txn.cashback

    def _refund(self, txn, fields):
        backend = self.wallet_backend
        if backend is None or not txn.wallet_charged or txn.refunded or txn.user is None:
            return None
        # A reversal after cashback was paid refunds the net amount, so the
        # customer never keeps cashback for an undelivered product.
        amount = txn.amount_charged - (txn.cashback if txn.cashback_paid else Decimal("0"))
        if amount > 0:
            backend.credit(
                txn.user, amount, reference=f"vtpass:refund:{txn.request_id}",
                kind=WalletEntryKind.REFUND, description=f"Refund for {self._describe(txn)}", transaction=txn,
            )
        txn.refunded = True
        txn.refund_amount = max(amount, Decimal("0"))
        fields.update({"refunded", "refund_amount"})
        return txn.refund_amount

    def _emit(self, txn, old_status, new_status, refund_amount, cashback_amount):
        from vtpass.models import Transaction

        def send():
            signals.transaction_status_changed.send(
                sender=Transaction, transaction=txn, old_status=old_status, new_status=new_status
            )
            specific = signals.STATUS_SIGNALS.get(str(new_status))
            if specific is not None:
                specific.send(sender=Transaction, transaction=txn)
            if refund_amount:
                signals.transaction_refunded.send(sender=Transaction, transaction=txn, amount=refund_amount)
            if cashback_amount:
                signals.cashback_paid.send(sender=Transaction, transaction=txn, amount=cashback_amount)

        db_transaction.on_commit(send)

    # ---- requery ---------------------------------------------------------------------
    def requery(self, txn):
        """Ask VTpass for the latest status and apply it. Returns the updated transaction."""
        from vtpass.models import Transaction

        try:
            response = self.client.requery(txn.request_id)
        except VTpassError as exc:
            Transaction.objects.filter(pk=txn.pk).update(
                requery_count=F("requery_count") + 1,
                last_requeried_at=timezone.now(),
                error_message=str(exc)[:2000],
            )
            txn.refresh_from_db()
            if txn.is_open:
                self.transition(txn, Status.PENDING)
            return txn

        Transaction.objects.filter(pk=txn.pk).update(
            requery_count=F("requery_count") + 1, last_requeried_at=timezone.now()
        )
        txn.refresh_from_db()

        if response.code == ResponseCode.INVALID_REQUEST_ID:
            # VTpass never received this purchase.
            age_minutes = (timezone.now() - txn.created_at).total_seconds() / 60
            if txn.is_open and age_minutes >= vtpass_settings.REQUERY["FAIL_UNKNOWN_AFTER_MINUTES"]:
                return self.transition(txn, Status.FAILED, response=response,
                                       error="Transaction was not received by VTpass.")
            return self.transition(txn, Status.PENDING, response=response)
        return self.apply_response(txn, response)

    def requery_due(self, limit=None):
        """Requery open transactions whose next check is due. Returns the number processed."""
        from vtpass.models import Transaction

        limit = limit or vtpass_settings.REQUERY["BATCH_SIZE"]
        count = 0
        for txn in Transaction.objects.due_for_requery().order_by("next_requery_at", "created_at")[:limit]:
            try:
                self.requery(txn)
            except Exception:  # keep going; one bad row must not block the batch
                logger.exception("Requery failed for %s", txn.request_id)
            count += 1
        return count

    # ---- misc --------------------------------------------------------------------------
    @staticmethod
    def _describe(txn):
        target = txn.billers_code or txn.phone
        return f"{txn.product_name or txn.service_id} {target}".strip()[:255]

    @staticmethod
    def _save_beneficiary(txn):
        from vtpass.models import Beneficiary

        code = txn.billers_code or txn.phone
        if not code:
            return
        beneficiary, _ = Beneficiary.objects.get_or_create(
            user=txn.user, service_id=txn.service_id, billers_code=code,
            defaults={"category": txn.category},
        )
        name = txn.vend_details.get("customerName") or txn.vend_details.get("CustomerName") or ""
        beneficiary.use_count += 1
        beneficiary.last_used_at = timezone.now()
        if name and not beneficiary.customer_name:
            beneficiary.customer_name = str(name)[:255]
        beneficiary.save()
