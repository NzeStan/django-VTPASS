# Usage guide

```python
from vtpass.services import VTpass
vt = VTpass()
```

`VTpass()` is cheap to create. Pass `client=VTpassClient(api_key=..., ...)` to use different
credentials per tenant.

## The transaction object

Every purchase returns a `vtpass.models.Transaction`:

```python
txn.status              # initiated | pending | successful | failed | reversed
txn.request_id          # your VTpass request_id (also txn.reference)
txn.amount              # face value sent to VTpass
txn.fee, txn.discount, txn.amount_charged, txn.cashback
txn.cost                # what VTpass debited you (total_amount)
txn.vtpass_commission   # your VTpass commission
txn.profit              # amount_charged - cost - cashback paid
txn.token               # prepaid electricity token
txn.purchased_code      # VTpass purchased_code text (PINs, tokens)
txn.vend_details        # everything vended: units, cards, tokens, Voucher, certUrl...
txn.refunded, txn.refund_amount
```

A **pending** transaction is not a failure. Show "processing" and let requery or the webhook settle
it. The customer's money stays debited until VTpass says the purchase failed.

## Errors

```python
from vtpass.exceptions import (
    VTpassValidationError,   # bad input → show exc.message / exc.errors to the user
    InsufficientFunds,       # wallet balance too low
    PurchaseDenied,          # vetoed by a pre_purchase receiver (PIN, KYC...), LimitExceeded subclasses it
    VTpassMerchantError,     # your VTpass account needs attention (low balance, IP, whitelisting)
    VTpassNetworkError,      # VTpass unreachable (lookups only; purchases go pending instead)
    VTpassError,             # base class
)
```

## Product cheat sheet

| Product | Lookup | Buy |
|---|---|---|
| Airtime | `vt.airtime.networks()` | `vt.airtime.buy(phone, amount, network=None)` |
| Data | `vt.data.plans("mtn")`, `plans("glo", sme=True)` | `vt.data.buy(phone, variation_code, network=None)` |
| TV | `vt.tv.bouquets("dstv")`, `vt.tv.verify("dstv", card)` | `vt.tv.change(...)`, `vt.tv.renew(...)`, `vt.tv.showmax(phone, code)` |
| Electricity | `vt.electricity.discos()`, `verify(disco, meter, type)` | `vt.electricity.buy(disco, meter, type, amount, phone)` |
| WAEC | `vt.education.products()` | `waec_result_checker(phone, quantity)`, `waec_registration(phone, quantity)` |
| JAMB | `verify_jamb_profile(profile_id, "utme")` | `jamb(profile_id, variation_code, phone)` |
| Smile | `verify_smile_email(email)`, `verify_smile_account(id)` | `buy_smile(account_id, code, phone)` |
| Spectranet | `spectranet_plans()` | `buy_spectranet(phone, code, quantity)` |
| Motor insurance | `vt.insurance.plans()`, `options("color" / "engine-capacity" / "state" / "lga" / "brand" / "model", parent=)` | `third_party_motor(...)` |
| International | `countries()`, `product_types(cc)`, `operators(cc, type)`, `variations(op, type)` | `vt.international.buy(...)` |
| Personal accident | `vt.insurance.personal_accident_plans()` | `vt.insurance.personal_accident(...)` |
| Bank transfer | `vt.bank.banks()`, `vt.bank.verify_account(bank_code, account)` | `vt.bank.transfer(bank_code, account, amount, phone)` |
| Anything | `vt.verify(service_id, billers_code, type)`, `vt.catalog.variations(id)`, `vt.catalog.options(id, name)` | `vt.purchase(service_id=..., ...)` |

Bank transfers resolve the account name first (`verify=True` by default) and store it in
`transaction.metadata["account_name"]`. VTpass's transfer response has no explicit delivery status,
so a transfer stays *pending* (money held) until requery or the webhook confirms it.

Discos accept service IDs (`ikeja-electric`) or short names (`ikedc`, `ekedc`, `aedc`, `phed`,
`kedco`, `jed`, `ibedc`, `kaedco`, `eedc`, `bedc`, `aba`, `yedc`).

Common keyword arguments on every buy: `user`, `email`, `idempotency_key`, `metadata`, `channel`,
`request`, `charge_wallet=True`, `save_beneficiary=False`.

## Wallets

```python
from vtpass.wallets import fund_wallet, wallet_balance

# In your payment-gateway webhook, after verifying the payment:
fund_wallet(user, amount, reference=f"paystack:{reference}")   # idempotent per reference
wallet_balance(user)
```

Bring your own ledger:

```python
from vtpass.wallets import BaseWalletBackend

class CoreBankingWallet(BaseWalletBackend):
    def balance(self, user): ...
    def debit(self, user, amount, *, reference, kind, description="", transaction=None, metadata=None): ...
    def credit(self, user, amount, *, reference, kind, description="", transaction=None, metadata=None): ...

VTPASS = {"WALLET_BACKEND": "myapp.wallets.CoreBankingWallet"}
```

`debit` must raise `vtpass.exceptions.InsufficientFunds` and both methods must be idempotent per
`reference`.

## Pricing

Create rules in the admin (`VTpass › Pricing rules`), in code, or in settings:

```python
from vtpass.models import PricingRule

PricingRule.objects.create(name="Airtime 2% off", category="airtime",
                           discount_type="percent", discount_value=2, discount_cap=500)
PricingRule.objects.create(name="Electricity fee", category="electricity-bill",
                           fee_type="flat", fee_value=100)
PricingRule.objects.create(name="MTN data 3% cashback", service_id="mtn-data",
                           cashback_type="percent", cashback_value=3, cashback_cap=300)
PricingRule.objects.create(name="Agents", user_group=agents_group, category="airtime",
                           discount_value=4, priority=10)
```

Preview a price: `vt.quote("mtn", 1000, user=user).as_dict()`.

## Building an OPay-style bills app

1. **Wallet**: enable `ModelWalletBackend` and credit it from your card/transfer funding webhook.
2. **Transaction PIN**: veto purchases in a `pre_purchase` receiver (see [extending](extending.md)).
3. **Home screen**: `GET catalog/categories/`, `airtime/networks/`, `networks/detect/?phone=`.
4. **Forms**: plans (`data/plans/`), bouquets, discos, insurance options; verify before paying.
5. **Pay**: `POST airtime/` (etc.) with an `Idempotency-Key` header. Handle 201/202/422.
6. **Receipts**: enable notifications or listen to `transaction_successful`.
7. **History**: `GET transactions/`, `GET wallet/entries/`, `beneficiaries/`.
8. **Promos**: pricing rules with `starts_at`/`ends_at`, cashback, and group tiers for agents.
9. **Ops**: admin, earnings report, low-balance alerts, Celery beat for requery and sync.

## Raw clients (no database)

```python
from vtpass.client import VTpassClient
from vtpass.messaging import MessagingClient

c = VTpassClient(api_key="...", public_key="...", secret_key="...", sandbox=False)
c.get_balance(); c.get_variations("dstv"); c.verify("dstv", "1212121212")
r = c.pay(serviceID="mtn", amount=100, phone="08011111111")
r.status, r.code, r.vend_details
c.requery(r.request_id)

MessagingClient().send("0803...,0802...", "Hello", sender="MyBrand", route="dnd-fallback")
```

## Management commands

| Command | Purpose |
|---|---|
| `vtpass_sync_catalog [--category X] [--service Y] [--no-variations]` | Refresh the local catalogue |
| `vtpass_requery_pending [--reference R] [--limit N]` | Settle pending transactions |
| `vtpass_balance [--sms]` | Merchant balance (and SMS units) |
| `vtpass_send_sms <recipients> <message> [--sender] [--route]` | Send an SMS |
