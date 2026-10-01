# django-vtpass documentation

django-vtpass connects a Django project to everything VTpass offers and adds the backend pieces a
bills/VTU product needs around it.

## Layers

You can use any layer on its own:

| Layer | Module | Needs the database? | Use it when |
|---|---|---|---|
| HTTP clients | `vtpass.client.VTpassClient`, `vtpass.messaging.MessagingClient` | No | You only want typed access to the VTpass APIs |
| Services | `vtpass.services.VTpass` | Yes | You want purchases recorded, priced, paid and settled for you |
| Wallet backends | `vtpass.wallets` | Built-in one does | You want customers to pay from a balance |
| Pricing | `vtpass.pricing`, `PricingRule` model | Optional | You charge fees or give discounts/cashback |
| Webhook view | `vtpass.urls` | Yes | VTpass should push status updates to you |
| Jobs / Celery | `vtpass.jobs`, `vtpass.tasks` | Yes | Background requery, catalogue sync, notifications |
| Notifications | `vtpass.notifications` | Yes | Customers should get SMS/email receipts |
| REST API | `vtpass.api.urls` (DRF) | Yes | Your mobile/web frontend talks to Django |
| Admin | `vtpass.admin` | Yes | Ops staff need to see and manage transactions |

## Data model

- `Transaction`: one row per purchase, holding money breakdown, status, VTpass response, token/PINs and requery schedule.
- `ServiceCategory`, `Service`, `Variation`: the local catalogue cache.
- `PricingRule`: fees, discounts and cashback.
- `Wallet`, `WalletEntry`: the optional customer wallet and its append-only ledger.
- `Beneficiary`: saved phones, meters and smartcards per user.
- `WebhookEvent`: audit log of VTpass callbacks.
- `SMSMessage`: log of messages sent through VTpass Messaging.

Public identifiers are random UUIDs (`uid`). Integer primary keys are never exposed through the API.

## Transaction statuses

`initiated → pending → successful | failed`, and `successful → reversed`. Failed and reversed are
final. Illegal moves (e.g. failed → successful from a late callback) are ignored and logged.

## Guides

- [Installation](installation.md)
- [Configuration](configuration.md)
- [Usage](usage.md)
- [Extending: signals, notifications, Celery, custom backends](extending.md)
- [REST API](api.md)
