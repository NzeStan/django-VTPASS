"""
Pytest configuration for the VTpass tests.
This module provides common fixtures for the VTpass tests.
"""

import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.utils import timezone

from vtpass.models import (
    Transaction, Service, ServiceVariation, Provider,
    Commission, CommissionRate, Wallet, WalletTransaction
)
from vtpass.constants import ServiceType, TransactionStatus, NetworkProvider


User = get_user_model()


@pytest.fixture
def user():
    """Create a test user."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='password'
    )


@pytest.fixture
def admin_user():
    """Create a test admin user."""
    return User.objects.create_superuser(
        username='adminuser',
        email='admin@example.com',
        password='password'
    )


@pytest.fixture
def provider():
    """Create a test provider."""
    return Provider.objects.create(
        name='MTN',
        code='mtn',
        service_type=ServiceType.AIRTIME,
        description='MTN Nigeria'
    )


@pytest.fixture
def service(provider):
    """Create a test service."""
    return Service.objects.create(
        name='MTN Airtime',
        service_id='mtn',
        service_type=ServiceType.AIRTIME,
        provider=provider,
        description='MTN Airtime',
        min_amount=Decimal('50'),
        max_amount=Decimal('50000')
    )


@pytest.fixture
def service_variation(service):
    """Create a test service variation."""
    return ServiceVariation.objects.create(
        service=service,
        name='MTN Airtime',
        variation_code='mtn',
        description='MTN Airtime',
        amount=Decimal('100')
    )


@pytest.fixture
def transaction(service, service_variation, user):
    """Create a test transaction."""
    return Transaction.objects.create(
        reference='test-reference',
        transaction_id='test-transaction-id',
        amount=Decimal('100'),
        status=TransactionStatus.PENDING,
        service_type=ServiceType.AIRTIME,
        service=service,
        service_variation=service_variation,
        phone='08012345678',
        email='test@example.com',
        user=user,
        customer_data={'provider': 'mtn'}
    )


@pytest.fixture
def completed_transaction(service, service_variation, user):
    """Create a completed test transaction."""
    return Transaction.objects.create(
        reference='test-completed-reference',
        transaction_id='test-completed-transaction-id',
        amount=Decimal('100'),
        status=TransactionStatus.COMPLETED,
        service_type=ServiceType.AIRTIME,
        service=service,
        service_variation=service_variation,
        phone='08012345678',
        email='test@example.com',
        user=user,
        customer_data={'provider': 'mtn'},
        completed_at=timezone.now()
    )


@pytest.fixture
def failed_transaction(service, service_variation, user):
    """Create a failed test transaction."""
    return Transaction.objects.create(
        reference='test-failed-reference',
        transaction_id='test-failed-transaction-id',
        amount=Decimal('100'),
        status=TransactionStatus.FAILED,
        service_type=ServiceType.AIRTIME,
        service=service,
        service_variation=service_variation,
        phone='08012345678',
        email='test@example.com',
        user=user,
        customer_data={'provider': 'mtn'},
        response_message='Transaction failed'
    )


@pytest.fixture
def commission_rate():
    """Create a test commission rate."""
    return CommissionRate.objects.create(
        service_type=ServiceType.AIRTIME,
        rate=Decimal('0.02'),
        description='Airtime commission rate'
    )


@pytest.fixture
def commission(transaction, user, commission_rate):
    """Create a test commission."""
    return Commission.objects.create(
        transaction=transaction,
        amount=Decimal('2'),
        rate=Decimal('0.02'),
        user=user,
        description='Test commission'
    )


@pytest.fixture
def wallet(user):
    """Create a test wallet."""
    return Wallet.objects.create(
        user=user,
        balance=Decimal('1000')
    )


@pytest.fixture
def wallet_transaction(wallet):
    """Create a test wallet transaction."""
    return WalletTransaction.objects.create(
        wallet=wallet,
        amount=Decimal('100'),
        transaction_type=WalletTransaction.TransactionType.DEPOSIT,
        description='Test deposit'
    )


@pytest.fixture
def mock_response_success():
    """Create a mock successful response."""
    return {
        'code': '000',
        'response_description': 'Success',
        'requestId': 'test-request-id',
        'content': {
            'transactions': {
                'status': 'delivered',
                'transactionId': 'test-transaction-id',
                'product_name': 'MTN Airtime',
                'unit_price': 100,
                'quantity': 1,
                'total_amount': 100,
                'phone': '08012345678',
                'email': 'test@example.com',
                'method': 'api'
            }
        },
        'transaction_date': {
            'date': '2023-01-01 12:00:00',
            'timezone_type': 3,
            'timezone': 'Africa/Lagos'
        },
        'purchased_code': ''
    }


@pytest.fixture
def mock_response_pending():
    """Create a mock pending response."""
    return {
        'code': '099',
        'response_description': 'Transaction pending',
        'requestId': 'test-request-id',
        'content': {
            'transactions': {
                'status': 'pending',
                'transactionId': 'test-transaction-id',
                'product_name': 'MTN Airtime',
                'unit_price': 100,
                'quantity': 1,
                'total_amount': 100,
                'phone': '08012345678',
                'email': 'test@example.com',
                'method': 'api'
            }
        },
        'transaction_date': {
            'date': '2023-01-01 12:00:00',
            'timezone_type': 3,
            'timezone': 'Africa/Lagos'
        },
        'purchased_code': ''
    }


@pytest.fixture
def mock_response_failed():
    """Create a mock failed response."""
    return {
        'code': '100',
        'response_description': 'Transaction failed',
        'requestId': 'test-request-id',
        'content': {}
    }


@pytest.fixture
def mock_service_categories():
    """Create mock service categories response."""
    return {
        'code': '000',
        'response_description': 'Success',
        'content': {
            'services': [
                {
                    'serviceID': 'mtn',
                    'name': 'MTN Airtime',
                    'serviceType': 'airtime',
                    'description': 'MTN Airtime',
                    'minimumAmount': 50,
                    'maximumAmount': 50000
                },
                {
                    'serviceID': 'mtn-data',
                    'name': 'MTN Data',
                    'serviceType': 'data',
                    'description': 'MTN Data Bundle',
                    'minimumAmount': 50,
                    'maximumAmount': 50000
                }
            ]
        }
    }


@pytest.fixture
def mock_service_variations():
    """Create mock service variations response."""
    return {
        'code': '000',
        'response_description': 'Success',
        'content': {
            'variations': [
                {
                    'variation_code': 'mtn-100',
                    'name': 'MTN 100 MB',
                    'variation_amount': 100,
                    'variation_desc': '100 MB data plan'
                },
                {
                    'variation_code': 'mtn-1gb',
                    'name': 'MTN 1 GB',
                    'variation_amount': 1000,
                    'variation_desc': '1 GB data plan'
                }
            ]
        }
    }