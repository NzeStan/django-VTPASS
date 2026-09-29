"""
Tests for the VTpass models.
This module provides tests for the VTpass models.
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
def commission_rate():
    """Create a test commission rate."""
    return CommissionRate.objects.create(
        service_type=ServiceType.AIRTIME,
        rate=Decimal('0.02'),
        description='Airtime commission rate'
    )


@pytest.fixture
def commission(transaction, user):
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


class TestProvider:
    """Tests for the Provider model."""
    
    def test_create_provider(self, provider):
        """Test creating a provider."""
        assert provider.name == 'MTN'
        assert provider.code == 'mtn'
        assert provider.service_type == ServiceType.AIRTIME
        assert provider.description == 'MTN Nigeria'
        assert provider.active is True
        
    def test_get_by_code(self, provider):
        """Test getting a provider by code."""
        found_provider = Provider.get_by_code(provider.code)
        assert found_provider == provider
        
    def test_get_providers_by_service_type(self, provider):
        """Test getting providers by service type."""
        providers = Provider.get_providers_by_service_type(ServiceType.AIRTIME)
        assert provider in providers


class TestService:
    """Tests for the Service model."""
    
    def test_create_service(self, service, provider):
        """Test creating a service."""
        assert service.name == 'MTN Airtime'
        assert service.service_id == 'mtn'
        assert service.service_type == ServiceType.AIRTIME
        assert service.provider == provider
        assert service.description == 'MTN Airtime'
        assert service.min_amount == Decimal('50')
        assert service.max_amount == Decimal('50000')
        assert service.active is True
        
    def test_get_by_service_id(self, service):
        """Test getting a service by service ID."""
        found_service = Service.get_by_service_id(service.service_id)
        assert found_service == service
        
    def test_get_services_by_type(self, service):
        """Test getting services by type."""
        services = Service.get_services_by_type(ServiceType.AIRTIME)
        assert service in services
        
    def test_has_variations(self, service, service_variation):
        """Test checking if a service has variations."""
        assert service.has_variations() is True
        
    def test_get_variations(self, service, service_variation):
        """Test getting variations for a service."""
        variations = service.get_variations()
        assert service_variation in variations


class TestServiceVariation:
    """Tests for the ServiceVariation model."""
    
    def test_create_service_variation(self, service_variation, service):
        """Test creating a service variation."""
        assert service_variation.service == service
        assert service_variation.name == 'MTN Airtime'
        assert service_variation.variation_code == 'mtn'
        assert service_variation.description == 'MTN Airtime'
        assert service_variation.amount == Decimal('100')
        assert service_variation.active is True
        
    def test_get_by_code(self, service_variation, service):
        """Test getting a variation by code."""
        found_variation = ServiceVariation.get_by_code(
            service, service_variation.variation_code
        )
        assert found_variation == service_variation
        
    def test_get_variations_for_service(self, service_variation, service):
        """Test getting variations for a service."""
        variations = ServiceVariation.get_variations_for_service(service)
        assert service_variation in variations


class TestTransaction:
    """Tests for the Transaction model."""
    
    def test_create_transaction(self, transaction, service, service_variation, user):
        """Test creating a transaction."""
        assert transaction.reference == 'test-reference'
        assert transaction.transaction_id == 'test-transaction-id'
        assert transaction.amount == Decimal('100')
        assert transaction.status == TransactionStatus.PENDING
        assert transaction.service_type == ServiceType.AIRTIME
        assert transaction.service == service
        assert transaction.service_variation == service_variation
        assert transaction.phone == '08012345678'
        assert transaction.email == 'test@example.com'
        assert transaction.user == user
        assert transaction.customer_data == {'provider': 'mtn'}
        
    def test_is_pending(self, transaction):
        """Test checking if a transaction is pending."""
        assert transaction.is_pending is True
        assert transaction.is_completed is False
        assert transaction.is_failed is False
        assert transaction.is_reversed is False
        
    def test_is_completed(self, transaction):
        """Test checking if a transaction is completed."""
        transaction.status = TransactionStatus.COMPLETED
        transaction.save()
        assert transaction.is_pending is False
        assert transaction.is_completed is True
        assert transaction.is_failed is False
        assert transaction.is_reversed is False
        
    def test_get_by_reference(self, transaction):
        """Test getting a transaction by reference."""
        found_transaction = Transaction.get_by_reference(transaction.reference)
        assert found_transaction == transaction
        
    def test_get_by_transaction_id(self, transaction):
        """Test getting a transaction by transaction ID."""
        found_transaction = Transaction.get_by_transaction_id(transaction.transaction_id)
        assert found_transaction == transaction
        
    def test_get_user_transactions(self, transaction, user):
        """Test getting transactions for a user."""
        transactions = Transaction.get_user_transactions(user)
        assert transaction in transactions
        
    def test_get_transactions_by_service_type(self, transaction):
        """Test getting transactions by service type."""
        transactions = Transaction.get_transactions_by_service_type(ServiceType.AIRTIME)
        assert transaction in transactions


class TestCommissionRate:
    """Tests for the CommissionRate model."""
    
    def test_create_commission_rate(self, commission_rate):
        """Test creating a commission rate."""
        assert commission_rate.service_type == ServiceType.AIRTIME
        assert commission_rate.rate == Decimal('0.02')
        assert commission_rate.rate_percentage == 2
        assert commission_rate.description == 'Airtime commission rate'
        assert commission_rate.active is True
        
    def test_get_rate_for_service_type(self, commission_rate):
        """Test getting a rate for a service type."""
        rate = CommissionRate.get_rate_for_service_type(ServiceType.AIRTIME)
        assert rate == Decimal('0.02')
        
    def test_calculate_commission(self, commission_rate):
        """Test calculating a commission."""
        amount = Decimal('100')
        commission = CommissionRate.calculate_commission(amount, ServiceType.AIRTIME)
        assert commission == Decimal('2')


class TestCommission:
    """Tests for the Commission model."""
    
    def test_create_commission(self, commission, transaction, user):
        """Test creating a commission."""
        assert commission.transaction == transaction
        assert commission.amount == Decimal('2')
        assert commission.rate == Decimal('0.02')
        assert commission.rate_percentage == 2
        assert commission.user == user
        assert commission.is_paid is False
        assert commission.paid_at is None
        assert commission.description == 'Test commission'
        
    def test_get_unpaid_commissions(self, commission):
        """Test getting unpaid commissions."""
        commissions = Commission.get_unpaid_commissions()
        assert commission in commissions
        
    def test_get_total_commission(self, commission):
        """Test getting total commission."""
        total = Commission.get_total_commission()
        assert total == Decimal('2')
        
    def test_create_from_transaction(self, transaction, commission_rate, user):
        """Test creating a commission from a transaction."""
        # Delete the existing commission to avoid unique constraint violation
        Commission.objects.all().delete()
        
        commission = Commission.create_from_transaction(transaction)
        assert commission.transaction == transaction
        assert commission.amount == Decimal('2')
        assert commission.rate == Decimal('0.02')
        assert commission.user == user


class TestWallet:
    """Tests for the Wallet model."""
    
    def test_create_wallet(self, wallet, user):
        """Test creating a wallet."""
        assert wallet.user == user
        assert wallet.balance == Decimal('1000')
        assert wallet.active is True
        
    def test_get_or_create_for_user(self, user):
        """Test getting or creating a wallet for a user."""
        # Delete the existing wallet to test creation
        Wallet.objects.filter(user=user).delete()
        
        wallet = Wallet.get_or_create_for_user(user)
        assert wallet.user == user
        assert wallet.balance == Decimal('0')
        assert wallet.active is True
        
    def test_deposit(self, wallet):
        """Test depositing funds into a wallet."""
        initial_balance = wallet.balance
        transaction = wallet.deposit(Decimal('100'), 'Test deposit')
        
        # Refresh the wallet from the database
        wallet.refresh_from_db()
        
        assert wallet.balance == initial_balance + Decimal('100')
        assert transaction.wallet == wallet
        assert transaction.amount == Decimal('100')
        assert transaction.transaction_type == WalletTransaction.TransactionType.DEPOSIT
        assert transaction.description == 'Test deposit'
        assert wallet.last_deposit_at is not None
        
    def test_withdraw(self, wallet):
        """Test withdrawing funds from a wallet."""
        initial_balance = wallet.balance
        transaction = wallet.withdraw(Decimal('100'), 'Test withdrawal')
        
        # Refresh the wallet from the database
        wallet.refresh_from_db()
        
        assert wallet.balance == initial_balance - Decimal('100')
        assert transaction.wallet == wallet
        assert transaction.amount == Decimal('100')
        assert transaction.transaction_type == WalletTransaction.TransactionType.WITHDRAWAL
        assert transaction.description == 'Test withdrawal'
        assert wallet.last_withdrawal_at is not None
        
    def test_withdraw_insufficient_balance(self, wallet):
        """Test withdrawing with insufficient balance."""
        with pytest.raises(ValueError, match='Insufficient balance'):
            wallet.withdraw(Decimal('2000'), 'Test withdrawal')
            
    def test_get_transactions(self, wallet, wallet_transaction):
        """Test getting transactions for a wallet."""
        transactions = wallet.get_transactions()
        assert wallet_transaction in transactions


class TestWalletTransaction:
    """Tests for the WalletTransaction model."""
    
    def test_create_wallet_transaction(self, wallet_transaction, wallet):
        """Test creating a wallet transaction."""
        assert wallet_transaction.wallet == wallet
        assert wallet_transaction.amount == Decimal('100')
        assert wallet_transaction.transaction_type == WalletTransaction.TransactionType.DEPOSIT
        assert wallet_transaction.description == 'Test deposit'
        
    def test_is_deposit(self, wallet_transaction):
        """Test checking if a transaction is a deposit."""
        assert wallet_transaction.is_deposit is True
        assert wallet_transaction.is_withdrawal is False
        
    def test_is_withdrawal(self, wallet_transaction):
        """Test checking if a transaction is a withdrawal."""
        wallet_transaction.transaction_type = WalletTransaction.TransactionType.WITHDRAWAL
        wallet_transaction.save()
        
        assert wallet_transaction.is_deposit is False
        assert wallet_transaction.is_withdrawal is True
        
    def test_get_by_reference(self, wallet_transaction):
        """Test getting a transaction by reference."""
        wallet_transaction.reference = 'test-reference'
        wallet_transaction.save()
        
        found_transaction = WalletTransaction.get_by_reference(wallet_transaction.reference)
        assert found_transaction == wallet_transaction
        
    def test_get_user_transactions(self, wallet_transaction, user):
        """Test getting transactions for a user."""
        transactions = WalletTransaction.get_user_transactions(user)
        assert wallet_transaction in transactions