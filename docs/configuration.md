# Configuration reference

All settings live in one `VTPASS` dict. Every key is optional. Nested dicts (`MESSAGING`, `LIMITS`,
`REQUERY`, `WEBHOOK`, `NOTIFICATIONS`, `API`) are merged with the defaults, so you only write what
you change. Settings are read lazily, and tests can use `override_settings(VTPASS=...)`.

## Credentials and environment

| Key | Default | Notes |
|---|---|---|
| `API_KEY` | `""` | Static API key |
| `PUBLIC_KEY` | `""` | `PK_...`, sent on GET requests |
| `SECRET_KEY` | `""` | `SK_...`, sent on POST requests |
| `AUTH_METHOD` | `"api_key"` | or `"basic"` (legacy email/password) |
| `USERNAME` / `PASSWORD` | `""` | Only for basic auth |
| `SANDBOX` | `True` | `False` uses `https://vtpass.com/api/` |
| `BASE_URL` | `None` | Override the API base (e.g. an egress proxy) |

## HTTP

| Key | Default | Notes |
|---|---|---|
| `CONNECT_TIMEOUT` / `READ_TIMEOUT` | `10` / `60` | Seconds |
| `VERIFY_SSL` | `True` | |
| `MAX_RETRIES` / `RETRY_BACKOFF` | `3` / `0.5` | GET requests only. Purchases are never auto-retried |
| `USER_AGENT` | `None` | Defaults to `django-vtpass/<version>` |
| `REQUEST_ID_SUFFIX_LENGTH` | `12` | Random part after the `YYYYMMDDHHMM` Lagos timestamp |
| `TRUSTED_IP_HEADER` | `None` | e.g. `"HTTP_X_FORWARDED_FOR"` behind a trusted proxy |

## Money

| Key | Default | Notes |
|---|---|---|
| `WALLET_BACKEND` | `None` | `"vtpass.wallets.ModelWalletBackend"` or your own class path |
| `PRICING_BACKEND` | `"vtpass.pricing.RuleBasedPricing"` | `"vtpass.pricing.FlatPricing"` disables pricing |
| `PRICING_RULES` | `[]` | Code-defined rules (same fields as `PricingRule`); DB rules win |
| `CASHBACK_ENABLED` | `True` | Global cashback switch |
| `CURRENCY` | `"NGN"` | |
| `LIMITS.MIN_AMOUNT` / `MAX_AMOUNT` | `None` | Per-transaction face value bounds (combined with catalogue limits) |
| `LIMITS.DAILY_AMOUNT_PER_USER` | `None` | Sum of `amount_charged` today, excluding failed/reversed |
| `LIMITS.DAILY_COUNT_PER_USER` | `None` | |

## Settlement

| Key | Default | Notes |
|---|---|---|
| `REQUERY.SCHEDULE` | `[30, 60, 120, 300, 600, 1800, 3600, ...]` | Seconds between requeries of a pending transaction |
| `REQUERY.FAIL_UNKNOWN_AFTER_MINUTES` | `10` | VTpass answers `015` when it never received a purchase. Only then, and only after this delay, is it failed and refunded |
| `REQUERY.BATCH_SIZE` | `100` | Per `requery_pending` run |
| `LOW_BALANCE_THRESHOLD` | `None` | Emits `merchant_balance_low` when the VTpass balance drops below it |

## Webhook

| Key | Default | Notes |
|---|---|---|
| `WEBHOOK.TOKEN` | `""` | Secret path segment. **Set it in production** (a system check warns if it's empty) |
| `WEBHOOK.ALLOWED_IPS` | `[]` | Optional source allowlist |
| `WEBHOOK.VERIFY_WITH_REQUERY` | `True` | Confirm every update with VTpass before acting. Keep this on |
| `WEBHOOK.STORE_EVENTS` | `True` | Keep a `WebhookEvent` audit row (deduplicated) |

## Messaging (bulk SMS)

| Key | Default | Notes |
|---|---|---|
| `MESSAGING.PUBLIC_KEY` / `SECRET_KEY` | `""` | `VT_PK_...` / `VT_SK_...` from the Messaging dashboard |
| `MESSAGING.DEFAULT_SENDER` | `""` | Registered sender ID |
| `MESSAGING.DEFAULT_ROUTE` | `"normal"` | `normal`, `dnd`, `dnd-fallback`, `simhost`, `simhost-fallback` |
| `MESSAGING.API_VERSION` | `2` | v2 (POST) where available. SIMHOST routes always use v1 |
| `MESSAGING.LOG_MESSAGES` | `True` | Store `SMSMessage` rows |

## Async and notifications

| Key | Default | Notes |
|---|---|---|
| `USE_CELERY` | `False` | Run jobs through `vtpass.tasks` |
| `CELERY_QUEUE` | `None` | Route vtpass tasks to a dedicated queue |
| `NOTIFICATIONS.ENABLED` | `False` | |
| `NOTIFICATIONS.BACKENDS` | `[]` | e.g. `["vtpass.notifications.backends.SMSBackend", "vtpass.notifications.backends.EmailBackend"]` |
| `NOTIFICATIONS.EVENTS` | successful, failed, reversed | Add `"transaction.pending"` if wanted |
| `NOTIFICATIONS.TEMPLATES` | `{}` | `{"transaction.successful": {"sms": "...", "subject": "...", "body": "..."}}` |
| `NOTIFICATIONS.SMS_SENDER` / `SMS_ROUTE` / `EMAIL_FROM` | `None` | Overrides |
| `NOTIFICATIONS.ASYNC` | `True` | Dispatch through Celery when enabled |

Template placeholders: `{product} {service_id} {amount} {amount_charged} {currency} {target} {phone}
{reference} {status} {token} {units} {cashback} {vend_text} {refund_text}`.

## REST API

| Key | Default |
|---|---|
| `API.PERMISSION_CLASSES` | `["rest_framework.permissions.IsAuthenticated"]` |
| `API.ADMIN_PERMISSION_CLASSES` | `["rest_framework.permissions.IsAdminUser"]` |
| `API.PURCHASE_THROTTLE_RATE` | `"30/min"` per user (`None` disables) |
| `API.VERIFY_THROTTLE_RATE` | `"60/min"` per user |
| `API.ALLOW_GENERIC_PURCHASE` | `True`; set `False` to hide `POST purchase/` |

## Misc

| Key | Default | Notes |
|---|---|---|
| `CATALOG_CACHE_TIMEOUT` | `3600` | Seconds to cache API lookups (uses Django's cache) |
| `LOGGER_NAME` | `"vtpass"` | |
| `LOG_REQUESTS` | `True` | Logs requests/responses with secrets and vended codes masked |
| `STORE_RAW_RESPONSES` | `True` | Keep the last VTpass response on each transaction |
| `BENEFICIARIES_ENABLED` | `True` | Allow `save_beneficiary=True` |
