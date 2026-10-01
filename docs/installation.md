# Installation

## 1. Install

```bash
pip install django-vtpass              # core: client, services, models, webhook, admin
pip install "django-vtpass[drf]"       # + REST API
pip install "django-vtpass[celery]"    # + Celery tasks
pip install "django-vtpass[all]"       # everything
```

## 2. Configure Django

```python
INSTALLED_APPS = [
    # ...
    "rest_framework",   # only if you use the REST API
    "vtpass",
]

VTPASS = {
    "API_KEY": os.environ["VTPASS_API_KEY"],
    "PUBLIC_KEY": os.environ["VTPASS_PUBLIC_KEY"],
    "SECRET_KEY": os.environ["VTPASS_SECRET_KEY"],
    "SANDBOX": True,
    "WEBHOOK": {"TOKEN": os.environ["VTPASS_WEBHOOK_TOKEN"]},
}
```

Never commit keys. Load them from the environment or a secrets manager.

## 3. URLs

```python
urlpatterns = [
    path("vtpass/", include("vtpass.urls")),            # webhook endpoint
    path("api/vtpass/", include("vtpass.api.urls")),    # optional REST API
]
```

## 4. Database

```bash
python manage.py migrate
python manage.py check      # warns about missing keys, an empty webhook token in live mode, etc.
```

Use PostgreSQL (or MySQL) in production: wallet safety relies on `SELECT ... FOR UPDATE`. If you
use SQLite (development only) with threads or several workers, set
`"OPTIONS": {"transaction_mode": "IMMEDIATE"}` (Django 5.1+) to avoid "database is locked" errors.

## 5. VTpass dashboard checklist

Do this on both sandbox.vtpass.com and vtpass.com:

1. **API Keys** tab: set "API authentication type" to *API keys* (or *all*), copy the API key, then
   generate the public/secret pair. The secret is shown only once.
2. **Product Settings**: whitelist every product you plan to sell. Otherwise you get error `028`.
3. **IP whitelisting**: send your server's outbound IP to VTpass support. Otherwise you get error `027`.
4. **Callback URL**: `https://<your-domain>/vtpass/webhook/<VTPASS["WEBHOOK"]["TOKEN"]>/`.
5. **Messaging** (for SMS): copy the `VT_PK_`/`VT_SK_` keys from the Messaging dashboard into
   `VTPASS["MESSAGING"]` and register your sender ID.

## 6. Background work

With Celery:

```python
VTPASS = {..., "USE_CELERY": True}
CELERY_BEAT_SCHEDULE = {
    "vtpass-requery-pending": {"task": "vtpass.requery_pending", "schedule": 60},
    "vtpass-sync-catalog": {"task": "vtpass.sync_catalog", "schedule": 6 * 60 * 60},
    "vtpass-check-balance": {"task": "vtpass.check_merchant_balance", "schedule": 15 * 60},
}
```

Without Celery, use cron:

```cron
* * * * *    python manage.py vtpass_requery_pending
0 */6 * * *  python manage.py vtpass_sync_catalog
*/15 * * * * python manage.py vtpass_balance
```

## 7. Sandbox test values

| Product | Value | Result |
|---|---|---|
| Airtime/data/Showmax phone | `08011111111` | success |
| | `201000000000` | pending |
| | `300000000000` | timeout |
| | anything else | failed |
| DStv/GOtv/Startimes smartcard, Spectranet | `1212121212` | success |
| Prepaid meter | `1111111111111` | success |
| Postpaid meter | `1010101010101` | success |
| JAMB profile ID | `0123456789` | success |
| Smile email | `tester@sandbox.com` | success |
| Bank account (`bank-deposit`) | `1234567890` | success |

These are also available as `vtpass.constants.Sandbox`.
