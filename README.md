# Django VTpass

A comprehensive Django package for integrating VTpass bill payment services into your Django projects. This package provides a complete and flexible way to handle all types of bill payments available on the VTpass platform.

## Features

- **Complete VTpass API Coverage**: Supports all bill services including airtime, data, electricity, cable TV, education, internet services, betting, and water bills.
- **Django REST Framework Integration**: Comes with a fully functional REST API for easy integration with frontend applications.
- **Advanced ORM Models**: Well-structured models for transactions, services, providers, commissions, and wallets.
- **Customizable Settings**: Highly configurable with sensible defaults.
- **Commission Management**: Built-in support for tracking and managing commissions.
- **Virtual Wallet System**: Integrated wallet for managing virtual funds.
- **Comprehensive Logging**: Detailed logging for debugging and audit purposes.
- **Error Handling**: Robust error handling and custom exceptions.
- **Django Signals**: Signals for various events to enable decoupled functionality.
- **Internationalization Ready**: Uses Django's translation system for multilingual support.
- **Admin Interface**: Sophisticated Django admin interface for managing all aspects of the package.
- **Well Tested**: Comprehensive test suite for all functionality.
- **UUID Support**: Configurable to use UUID primary keys instead of default IDs.
- **OOP Principles**: Follows object-oriented programming principles for clean code structure.

## Installation

```bash
pip install django-vtpass
```

Add `vtpass` to your `INSTALLED_APPS` in `settings.py`:

```python
INSTALLED_APPS = [
    # ...
    'rest_framework',
    'vtpass',
    # ...
]
```

Run migrations:

```bash
python manage.py migrate vtpass
```

## Configuration

Add the following to your Django settings:

```python
VTPASS = {
    'API_KEY': 'your-api-key',  # Required
    'SECRET_KEY': 'your-secret-key',  # Required
    'ENVIRONMENT': 'development',  # or 'production'
    'VERIFY_SSL': True,
    'TIMEOUT': 30,  # Request timeout in seconds
    'MAX_RETRIES': 3,
    'USE_UUID': False,  # Set to True to use UUID instead of ID
    'LOG_LEVEL': 'INFO',
    # Commission settings
    'COMMISSION': {
        'ENABLED': True,
        'DEFAULT_RATE': 0.02,  # 2%
        'RATES': {
            'airtime': 0.02,
            'data': 0.02,
            'electricity': 0.01,
            'cable': 0.01,
            'education': 0.015,
        },
    },
    'WEBHOOK': {
        'ENABLED': False,
        'URL': None,
        'SECRET': None,
        'TIMEOUT': 10,
    },
}
```

## URL Configuration

Add the URLs to your project's `urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    # ...
    path('vtpass/', include('vtpass.urls')),
    # ...
]
```

## Basic Usage

### Airtime Purchase

```python
from vtpass.services import AirtimeService

# Initialize the service
airtime_service = AirtimeService()

# Purchase airtime
transaction = airtime_service.purchase(
    phone="08012345678",
    amount=1000,
    provider="mtn",
    reference="my-unique-reference"  # Optional, auto-generated if not provided
)

print(f"Transaction status: {transaction.status}")
print(f"Transaction ID: {transaction.transaction_id}")
```

### Data Subscription

```python
from vtpass.services import DataService

# Initialize the service
data_service = DataService()

# Get available data plans for a provider
plans = data_service.get_data_plans("mtn")

# Purchase a data plan
transaction = data_service.purchase(
    phone="08012345678",
    provider="mtn",
    plan="mtn-1gb"  # Plan code from the available plans
)
```

### Electricity Bill Payment

```python
from vtpass.services import ElectricityService

# Initialize the service
electricity_service = ElectricityService()

# Verify a meter number
verification = electricity_service.verify_meter(
    meter_number="12345678901",
    provider="ikeja-electric",
    meter_type="prepaid"
)

# Pay electricity bill
transaction = electricity_service.purchase(
    meter_number="12345678901",
    amount=5000,
    provider="ikeja-electric",
    meter_type="prepaid",
    phone="08012345678"
)
```

### Cable TV Subscription

```python
from vtpass.services import CableTVService

# Initialize the service
cable_service = CableTVService()

# Verify a smartcard number
verification = cable_service.verify_smartcard(
    smartcard_number="12345678901",
    provider="dstv"
)

# Pay for subscription
transaction = cable_service.purchase(
    smartcard_number="12345678901",
    provider="dstv",
    plan="dstv-compact",
    phone="08012345678"
)
```

## API Usage

The package provides a full REST API that can be used with frontend applications. Here are some example API endpoints:

- `GET /vtpass/api/services/`: Get list of available services
- `GET /vtpass/api/providers/`: Get list of available providers
- `POST /vtpass/api/airtime/purchase/`: Purchase airtime
- `POST /vtpass/api/data/purchase/`: Purchase data subscription
- `POST /vtpass/api/electricity/verify_meter/`: Verify meter number
- `POST /vtpass/api/electricity/purchase/`: Pay electricity bill
- `GET /vtpass/api/transactions/`: Get list of transactions

Refer to the API documentation for more details on available endpoints and request/response formats.

## Commission System

The package includes a built-in commission system:

```python
from vtpass.models import Commission

# Get all commissions for a user
commissions = Commission.objects.filter(user=user)

# Get unpaid commissions
unpaid_commissions = Commission.get_unpaid_commissions(user=user)

# Get total commission amount
total = Commission.get_total_commission(
    user=user,
    start_date=start_date,
    end_date=end_date
)
```

## Wallet System

The package also includes a virtual wallet system:

```python
from vtpass.models import Wallet

# Get or create a wallet for a user
wallet = Wallet.get_or_create_for_user(user)

# Deposit funds
wallet.deposit(amount=1000, description="Deposit from bank")

# Withdraw funds
wallet.withdraw(amount=500, description="Withdrawal to bank")

# Get wallet transactions
transactions = wallet.get_transactions()
```

## Signals

The package defines several signals that you can connect to for custom functionality:

- `transaction_completed`: Fired when a transaction is completed
- `transaction_failed`: Fired when a transaction fails
- `transaction_status_changed`: Fired when a transaction status changes
- `commission_earned`: Fired when a commission is earned
- `wallet_changed`: Fired when a wallet balance changes

Example usage:

```python
from django.dispatch import receiver
from vtpass.signals import transaction_completed

@receiver(transaction_completed)
def handle_transaction_completed(sender, instance, **kwargs):
    # Do something when a transaction is completed
    # For example, send a notification to the user
    print(f"Transaction {instance.reference} completed")
```

## Testing

The package includes a comprehensive test suite. To run the tests:

```bash
pytest
```

Or using Django's test command:

```bash
python manage.py test vtpass
```

## License

This project is licensed under the MIT License.