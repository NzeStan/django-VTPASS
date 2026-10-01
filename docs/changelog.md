# Changelog

## 1.0.0 (unreleased)

Complete rewrite.

### Added
- Billing API client covering every documented endpoint: pay, requery, merchant-verify, Smile email
  lookup, balance, service categories, services, variations, product options, international airtime
  (countries, product types, operators, variations) and Universal Insurance options.
- Messaging client: normal, DND, DND-fallback, SIMHOST and SIMHOST-fallback routes, v1 and v2,
  delivery reports, client batch IDs and SMS unit balance.
- Purchase engine with a locked, idempotent wallet ledger, a status state machine, exactly-once
  refunds and cashback, reversal handling, requery scheduling with backoff, idempotency keys,
  daily limits and a `pre_purchase` veto signal.
- Product services: airtime (network auto-detection), data (incl. Glo SME), DStv/GOtv/Startimes/Showmax,
  electricity for all 12 discos, WAEC result checker and registration, JAMB, Smile, Spectranet,
  third-party motor and personal accident insurance, international airtime, bank transfers
  (bank list, account-name verification, transfer) and a generic purchase for any service ID.
- Pricing rules: convenience fees, instant discounts and cashback (flat or %, capped), targeted by
  category, service, plan, user group and amount band, with promo windows.
- Built-in wallet backend and a pluggable wallet interface.
- Secure webhook endpoint (token, IP allowlist, requery verification, deduplication).
- Catalogue sync with automatic updates from the `variations-update` webhook.
- Notifications (SMS, email, custom backends), optional Celery tasks and management commands.
- Optional DRF REST API with throttling, pagination and customer-safe error messages.
- Django admin with requery, sync and reprocess actions.

### Removed
- "Betting" and "water" products: VTpass does not offer either (they are not in its API documentation,
  website or sandbox). The HTML dashboard, request-logging middleware, decorators module and
  `Provider` model were also removed.
