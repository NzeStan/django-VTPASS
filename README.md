# django-vtpass

**The complete VTpass integration for Django.** Everything VTpass sells, from airtime, data, TV,
electricity, exam PINs, insurance, international airtime and bank transfers to bulk SMS, wired end to end with the
plumbing a real fintech app needs: customer wallets, fees, discounts, cashback, webhooks, automatic
requery, notifications, Celery, a REST API and an admin.

Building an OPay/PalmPay-style bills app? Install this, add your keys, and spend your time on the
product instead of the integration.

```bash
pip install django-vtpass            # core
pip install "django-vtpass[all]"     # + REST API (DRF) + Celery
```

---

## Why this package

| | |
|---|---|
| **Complete** | Every documented VTpass endpoint: pay, requery, verify, balance, categories, services, variations, options, Smile email lookup, international airtime (countries, product types, operators), bank transfer (bank list, account-name lookup, transfer), Universal Insurance lookups, and all 7 Messaging routes (normal, DND, DND-fallback, SIMHOST, SIMHOST-fallback, v1 and v2) plus SMS balance. Products VTpass adds later work through the generic purchase. |
| **Money-safe** | Decimal everywhere. Wallet rows are locked during debits and every ledger entry has a unique reference, so purchases can't overdraw and refunds or cashback can't be applied twice. Purchases are **never retried blindly** and a timeout is **never treated as failure**: unclear outcomes stay *pending* until requery or the webhook settles them. |
| **Secure** | Webhook secret token (constant-time compare), optional IP allowlist, and webhook payloads re-verified with VTpass before any money moves. Price-tampering protection, idempotency keys, per-user throttles and daily limits. Secrets, tokens and PINs are masked in logs, and merchant-side errors are never shown to customers. |
| **Optional by design** | Use only what you need: the raw HTTP client, the high-level services, the built-in wallet (or your own), pricing rules, notifications, Celery, the REST API, the admin. Each one is opt-in. |
| **Pluggable** | Extension points are Django signals (`pre_purchase` can veto, e.g. for PIN or KYC checks) and swappable backends for wallet, pricing and notifications. |
| **Scales** | Thread-local pooled HTTP sessions, no DB locks held during network I/O, indexed requery queue, cached catalogue, and Celery tasks with backoff. |

---

## Quick start

```python
# settings.py
INSTALLED_APPS = [..., "vtpass"]           # add "rest_framework" too if you use the API

VTPASS = {
    "API_KEY": env("VTPASS_API_KEY"),
    "PUBLIC_KEY": env("VTPASS_PUBLIC_KEY"),
    "SECRET_KEY": env("VTPASS_SECRET_KEY"),
    "SANDBOX": True,                                        # False in production
    "WALLET_BACKEND": "vtpass.wallets.ModelWalletBackend",  # optional built-in wallet
    "WEBHOOK": {"TOKEN": env("VTPASS_WEBHOOK_TOKEN")},
}

# urls.py
urlpatterns = [
    path("vtpass/", include("vtpass.urls")),             # webhook (no DRF needed)
    path("api/vtpass/", include("vtpass.api.urls")),     # optional REST API
]
```

```bash
python manage.py migrate
python manage.py vtpass_sync_catalog      # optional: cache categories, services and plans locally
```

Register `https://your-domain/vtpass/webhook/<WEBHOOK TOKEN>/` as the callback URL in your VTpass
dashboard, and whitelist your server IP and products there.

### Buy things

```python
from vtpass.services import VTpass

vt = VTpass()

# Airtime: the network is auto-detected from the number
txn = vt.airtime.buy("08031234567", 500, user=request.user)
txn.status            # "successful" | "pending" | "failed"

# Data
vt.data.plans("mtn")                                   # list plans
vt.data.buy("08031234567", "mtn-10mb-100", user=user)

# Electricity (prepaid token comes back in txn.token)
vt.electricity.verify("ikedc", "1111111111111", "prepaid")
txn = vt.electricity.buy("ikedc", "1111111111111", "prepaid", 5000, phone="08031234567", user=user)
txn.token, txn.vend_details["units"]

# TV
vt.tv.verify("dstv", "1212121212")                     # name, bouquet, Renewal_Amount
vt.tv.renew("dstv", "1212121212", phone="08031234567", user=user)
vt.tv.change("gotv", "1212121212", "gotv-max", phone="08031234567", user=user)
vt.tv.showmax("08031234567", "full", user=user)

# Education
vt.education.waec_result_checker("08031234567", quantity=2, user=user)   # vend_details["cards"]
vt.education.waec_registration("08031234567", user=user)
vt.education.verify_jamb_profile("0123456789", "utme")
vt.education.jamb("0123456789", "utme", "08031234567", user=user)

# Internet
vt.internet.verify_smile_email("tester@sandbox.com")
vt.internet.buy_smile("08011111111", "516", "08031234567", user=user)
vt.internet.buy_spectranet("08031234567", "spectranet-1000", quantity=1, user=user)

# Insurance (third-party motor)
vt.insurance.options("brand"); vt.insurance.options("model", parent="TOY")
vt.insurance.third_party_motor(plate_number="AAA123BB", variation_code="1", ..., user=user)

# Personal accident insurance
vt.insurance.personal_accident(variation_code="...", phone="0803...", full_name="Ada Obi",
                               address="Lagos", dob="1990-05-01", next_kin_name="Ngozi Obi",
                               next_kin_phone="0802...", business_occupation="Trader", user=user)

# Bank transfer (account name is always verified before money is sent)
vt.bank.banks()
vt.bank.verify_account("gtb", "1234567890")          # {"account_name": "..."}
vt.bank.transfer("gtb", "1234567890", 5000, phone="08031234567", user=user)

# International airtime and data
vt.international.countries()
vt.international.operators("GH", product_type_id=1)
vt.international.buy(recipient="233241234567", country_code="GH", operator_id="5",
                     product_type_id="1", variation_code="...", email="a@b.com",
                     phone="08031234567", amount=2000, user=user)

# Bulk SMS
vt.sms.send(["08031234567", "08021234567"], "Your OTP is 123456", sender="MyBrand")
vt.sms.send(numbers, "Hello", route="dnd")          # reach DND numbers
vt.sms.balance()

# Anything else VTpass offers, by service ID
vt.purchase(service_id="some-new-service", phone="0803...", amount=1000, billers_code="...")

vt.balance()             # your VTpass merchant balance
vt.quote("mtn", 1000)    # fee / discount / cashback / amount payable, without buying
```

Every `buy` call accepts `user`, `email`, `idempotency_key`, `metadata`, `charge_wallet`,
`save_beneficiary`, `channel` and `request`.

---

## How a purchase flows

```
quote ─► pre_purchase signal (PIN / KYC / fraud veto) ─► [DB txn: lock wallet, create Transaction, debit]
      ─► POST /api/pay (no locks held) ─► state machine:
            delivered  → SUCCESSFUL → cashback credited (once)
            failed     → FAILED     → refund credited (once)
            timeout / 099 / 5xx      → PENDING → requery (beat/cron/webhook) → settles later
            reversed (even after success) → REVERSED → refund net of cashback (once)
```

## Fees, commission and cashback

VTpass pays you a commission on each sale. **Pricing rules** (admin, DB, or settings) decide what you
do with that margin:

- **Convenience fee**: flat or %, with a minimum and a cap (e.g. ₦100 on electricity)
- **Instant discount**: flat or %, capped (e.g. 2% off airtime)
- **Cashback**: flat or %, capped, credited to the wallet after delivery (e.g. 3% back on data)

Rules can target a **category, service, single plan, user group** (agent/reseller tiers) and **amount
band**, and can be **time-boxed** for promos. The most specific rule wins, then priority. Every transaction
records `amount` (face value), `fee`, `discount`, `amount_charged`, `cashback`, VTpass `cost` and
`vtpass_commission`, and exposes `profit`. Staff get an earnings report at `GET reports/earnings/`.

## Optional pieces

| Feature | Turn on with |
|---|---|
| Built-in wallet | `"WALLET_BACKEND": "vtpass.wallets.ModelWalletBackend"`; fund it with `vtpass.wallets.fund_wallet(user, amount, reference)` from your Paystack/Flutterwave webhook |
| Your own ledger | Subclass `vtpass.wallets.BaseWalletBackend` |
| No wallet at all | Leave `WALLET_BACKEND` as `None` and take payment yourself before calling `buy` |
| Notifications (SMS/email/custom) | `"NOTIFICATIONS": {"ENABLED": True, "BACKENDS": [...]}` |
| Celery | `"USE_CELERY": True`, then add the beat schedule from `vtpass/tasks.py` |
| REST API | `pip install django-vtpass[drf]` and include `vtpass.api.urls` |
| Daily limits | `"LIMITS": {"DAILY_AMOUNT_PER_USER": "200000", "DAILY_COUNT_PER_USER": 50}` |
| Low merchant balance alert | `"LOW_BALANCE_THRESHOLD": 50000` → `merchant_balance_low` signal |

No Celery? Run `python manage.py vtpass_requery_pending` from cron every minute.

## Documentation

- [Installation](docs/installation.md)
- [Configuration reference](docs/configuration.md)
- [Usage guide (services, wallet, pricing, building an OPay-style app)](docs/usage.md)
- [Signals, notifications, Celery and custom backends](docs/extending.md)
- [REST API reference](docs/api.md)
- [Changelog](docs/changelog.md) · [Contributing](docs/contributing.md)

## What VTpass does not offer

Betting-wallet funding and water bills are **not** VTpass products. Neither appears in VTpass's API
documentation, the live site or the sandbox product list, so this package doesn't pretend to support
them. If VTpass adds them later, `vt.purchase(service_id=...)` works without a package update.

## Requirements

Python 3.9+ and Django 4.2+. DRF 3.14+ and Celery 5.3+ are optional. Tested on Django 4.2, 5.2 and 6.1.

## License

MIT
