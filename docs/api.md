# REST API reference

Mount it with `path("api/vtpass/", include("vtpass.api.urls"))` (requires `djangorestframework`).
Authentication is whatever your DRF project uses (session, token, JWT...). Permissions and
throttles are configured under `VTPASS["API"]`.

## Response envelope

```json
{"success": true, "message": "Transaction successful.", "data": {...}}
{"success": false, "message": "Insufficient balance: ...", "errors": {"amount": ["..."]}}
```

DRF field validation errors keep DRF's standard shape (`{"field": ["error"]}`) with status 400.
List endpoints return `data = {"count", "next", "previous", "results"}` (`?page=`, `?page_size=` up to 100).

## Purchase status codes

| HTTP | Meaning |
|---|---|
| 201 | Delivered (`data.status = "successful"`) |
| 202 | Processing (`pending`). Poll `transactions/<ref>/` or wait for a push |
| 422 | Failed or reversed. `message` says whether the customer was refunded |
| 400 | Invalid input |
| 402 | Insufficient wallet balance |
| 403 | Not allowed (`pre_purchase` veto, daily limit, permissions) |
| 409 | Conflict (duplicate) |
| 429 | Throttled |
| 503 | Service temporarily unavailable (merchant or config issue, details only in your logs) |

Send `Idempotency-Key: <uuid>` with every purchase. Retrying with the same key returns the original
transaction instead of buying again.

## Endpoints

### Catalogue and helpers
| Method | Path | Body / query |
|---|---|---|
| GET | `catalog/categories/` | |
| GET | `catalog/services/` | `?category=data` |
| GET | `catalog/services/<service_id>/variations/` | `?operator_id=&product_type_id=` (international) |
| GET | `catalog/services/<service_id>/options/` | `?name=passenger_type` |
| GET | `networks/detect/` | `?phone=0803...` → `{"network": "mtn"}` |
| POST | `verify/` | `{service_id, billers_code, type?}` |
| POST | `quote/` | `{service_id, amount?, variation_code?, quantity?}` |

### Products
| Method | Path | Body |
|---|---|---|
| GET | `airtime/networks/` | |
| POST | `airtime/` | `{phone, amount, network?}` |
| GET | `data/networks/`, `data/plans/?network=mtn[&sme=1]` | |
| POST | `data/` | `{phone, variation_code, network?, sme?}` |
| GET | `tv/providers/`, `tv/<provider>/bouquets/` | |
| POST | `tv/verify/` | `{provider, smartcard_number}` |
| POST | `tv/` | `{provider, action: "change" or "renew", smartcard_number, phone, variation_code?, quantity?}` (renew price is always verified server-side) |
| GET | `electricity/discos/` | |
| POST | `electricity/verify/` | `{disco, meter_number, meter_type}` |
| POST | `electricity/` | `{disco, meter_number, meter_type, amount, phone}` |
| GET | `education/products/` | |
| POST | `education/jamb/verify/` | `{profile_id, variation_code}` |
| POST | `education/` | `{product: "waec" / "waec-registration" / "jamb", phone, quantity?, variation_code?, profile_id?}` |
| GET | `internet/providers/` | |
| POST | `internet/smile/verify/` | `{email}` or `{account_id}` |
| POST | `internet/` | `{provider: "smile-direct" / "spectranet", phone, variation_code, account_id?, quantity?}` |
| GET | `insurance/plans/[?product=personal-accident-insurance]`, `insurance/options/<option>/?parent=` | option: `color`, `engine-capacity`, `state`, `lga`, `brand`, `model` |
| POST | `insurance/` | `{plate_number, variation_code, phone, email, insured_name, engine_capacity, chasis_number, vehicle_make, vehicle_color, vehicle_model, year_of_make, state, lga}` |
| POST | `insurance/personal-accident/` | `{variation_code, phone, full_name, address, dob (YYYY-MM-DD), next_kin_name, next_kin_phone, business_occupation}` |
| GET | `bank-transfer/banks/` | |
| POST | `bank-transfer/verify/` | `{bank_code, account_number}` → `{account_name}` |
| POST | `bank-transfer/` | `{bank_code, account_number, amount, phone}` (account re-verified server-side) |
| GET | `international/countries/`, `product-types/?country=`, `operators/?country=&product_type_id=`, `variations/?operator_id=&product_type_id=` | |
| POST | `international/` | `{recipient, country_code, operator_id, product_type_id, variation_code, phone, email, amount?}` |
| POST | `purchase/` | `{service_id, phone, amount?, billers_code?, variation_code?, quantity?, subscription_type?, extra?}` |

All purchase bodies also accept `email`, `save_beneficiary`, `metadata`.

### Account
| Method | Path | Notes |
|---|---|---|
| GET | `transactions/` | `?status=&service_id=&category=&search=`. Customers see their own; staff see all |
| GET | `transactions/<reference or id>/` | |
| POST | `transactions/<reference>/requery/` | Refresh a pending transaction |
| GET | `wallet/` | `{balance, currency}` |
| GET | `wallet/entries/` | `?kind=purchase/refund/cashback/funding` |
| GET, POST | `beneficiaries/` | `{service_id, billers_code, nickname?, category?, extra?}` |
| GET, PATCH, DELETE | `beneficiaries/<id>/` | |

### Admin (IsAdminUser by default)
| Method | Path |
|---|---|
| GET | `merchant/balance/` |
| GET | `reports/earnings/?start=YYYY-MM-DD&end=YYYY-MM-DD` |
| POST | `sms/send/` `{recipients: [...], message, sender?, route?, client_batch_id?}` |
| GET | `sms/balance/` |

## Example

```http
POST /api/vtpass/electricity/
Authorization: Bearer <token>
Idempotency-Key: 6f1c9a52-6a1f-4f0a-9a3e-3f2b0c1d2e4f
Content-Type: application/json

{"disco": "ikedc", "meter_number": "1111111111111", "meter_type": "prepaid",
 "amount": 5000, "phone": "08031234567"}
```

```json
{
  "success": true,
  "message": "Transaction successful.",
  "data": {
    "id": "0b6c...", "reference": "202510011230k3j2h1g9f8d7", "status": "successful",
    "service_id": "ikeja-electric", "amount": "5000.00", "fee": "100.00", "discount": "0.00",
    "amount_charged": "5100.00", "cashback": "0.00", "token": "26362054405982757802",
    "vend_details": {"units": "79.9 kWh", "mainToken": "26362054405982757802"}
  }
}
```
