"""
Tests for the Airtime service.
This module provides tests for the Airtime service.
"""

import pytest
import responses
from decimal import Decimal
from django.contrib.auth import get_user_model

from vtpass.services.airtime import AirtimeService
from vtpass.client import VTpassResponse
from vtpass.models import Transaction, Service, Provider
from vtpass.constants import ServiceType, NetworkProvider, Endpoints, TransactionStatus
from vtpass.exceptions import VTpassValidationError, VTpassServiceError


User = get_user_model()


@pytest.fixture
def service():
    """Create a test service instance."""
    return AirtimeService()


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
def mtn_service(provider):
    """Create a test MTN service."""
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
def mock_response():
    """Create a mock response."""
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


class TestAirtimeService:
    """Tests for the AirtimeService class."""
    
    def test_init(self, service):
        """Test initializing the service."""
        assert service.service_type == ServiceType.AIRTIME
        assert service.client is not None
    
    def test_get_providers(self, service):
        """Test getting providers."""
        providers = service.get_providers()
        
        assert len(providers) == 4  # MTN, Airtel, Glo, Etisalat
        assert providers[0]['id'] == NetworkProvider.MTN
        assert providers[0]['name'] == 'MTN'
    
    def test_get_service_id_for_provider(self, service):
        """Test getting service ID for a provider."""
        service_id = service.get_service_id_for_provider(NetworkProvider.MTN)
        
        assert service_id == 'mtn'
    
    def test_get_service_id_for_provider_invalid(self, service):
        """Test getting service ID for an invalid provider."""
        with pytest.raises(VTpassServiceError):
            service.get_service_id_for_provider('invalid-provider')
    
    def test_validate_purchase_data_valid(self, service):
        """Test validating valid purchase data."""
        data = {
            'phone': '08012345678',
            'amount': 100,
            'provider': NetworkProvider.MTN,
            'reference': 'test-reference'
        }
        
        validated_data = service.validate_purchase_data(data)
        
        assert validated_data == data
    
    def test_validate_purchase_data_invalid_phone(self, service):
        """Test validating purchase data with invalid phone."""
        data = {
            'phone': '0801',  # Too short
            'amount': 100,
            'provider': NetworkProvider.MTN,
            'reference': 'test-reference'
        }
        
        with pytest.raises(VTpassValidationError) as excinfo:
            service.validate_purchase_data(data)
        
        assert 'phone' in excinfo.value.errors
    
    def test_validate_purchase_data_invalid_amount(self, service):
        """Test validating purchase data with invalid amount."""
        data = {
            'phone': '08012345678',
            'amount': 10,  # Below minimum
            'provider': NetworkProvider.MTN,
            'reference': 'test-reference'
        }
        
        with pytest.raises(VTpassValidationError) as excinfo:
            service.validate_purchase_data(data)
        
        assert 'amount' in excinfo.value.errors
    
    def test_validate_purchase_data_invalid_provider(self, service):
        """Test validating purchase data with invalid provider."""
        data = {
            'phone': '08012345678',
            'amount': 100,
            'provider': 'invalid-provider',
            'reference': 'test-reference'
        }
        
        with pytest.raises(VTpassValidationError) as excinfo:
            service.validate_purchase_data(data)
        
        assert 'provider' in excinfo.value.errors
    
    @responses.activate
    def test_purchase_success(self, service, user, provider, mtn_service, mock_response):
        """Test making a successful purchase."""
        # Mock the API response
        responses.add(
            responses.POST,
            f'https://sandbox.vtpass.com/api/{Endpoints.PURCHASE}',
            json=mock_response,
            status=200
        )
        
        # Make the purchase
        transaction = service.purchase(
            phone='08012345678',
            amount=100,
            provider=NetworkProvider.MTN,
            reference='test-reference',
            user=user,
            email='test@example.com'
        )
        
        # Verify the transaction
        assert transaction.reference == 'test-reference'
        assert transaction.transaction_id == 'test-transaction-id'
        assert transaction.amount == Decimal('100')
        assert transaction.status == TransactionStatus.COMPLETED
        assert transaction.service_type == ServiceType.AIRTIME
        assert transaction.service.service_id == 'mtn'
        assert transaction.phone == '08012345678'
        assert transaction.email == 'test@example.com'
        assert transaction.user == user
    
    @responses.activate
    def test_purchase_api_error(self, service, user, provider, mtn_service):
        """Test handling an API error during purchase."""
        # Mock the API response
        error_response = {
            'code': '100',
            'response_description': 'API Error',
            'requestId': 'test-request-id',
            'content': {}
        }
        
        responses.add(
            responses.POST,
            f'https://sandbox.vtpass.com/api/{Endpoints.PURCHASE}',
            json=error_response,
            status=400
        )
        
        # Make the purchase and verify it raises an error
        with pytest.raises(VTpassServiceError) as excinfo:
            service.purchase(
                phone='08012345678',
                amount=100,
                provider=NetworkProvider.MTN,
                reference='test-reference',
                user=user,
                email='test@example.com'
            )
        
        assert 'API Error' in str(excinfo.value)
        
        # Verify the transaction was created but marked as failed
        transaction = Transaction.get_by_reference('test-reference')
        assert transaction is not None
        assert transaction.status == 'failed'
    
    @responses.activate
    def test_verify_transaction_success(self, service, user, provider, mtn_service, mock_response):
        """Test verifying a transaction successfully."""
        # Create a transaction to verify
        transaction = Transaction.objects.create(
            reference='test-reference',
            amount=Decimal('100'),
            status=TransactionStatus.PENDING,
            service_type=ServiceType.AIRTIME,
            service=mtn_service,
            phone='08012345678',
            email='test@example.com',
            user=user
        )
        
        # Mock the API response
        responses.add(
            responses.POST,
            f'https://sandbox.vtpass.com/api/{Endpoints.VERIFY_TRANSACTION}',
            json=mock_response,
            status=200
        )
        
        # Verify the transaction
        verified_transaction = service.verify_transaction('test-reference')
        
        # Check the transaction was updated
        assert verified_transaction.reference == 'test-reference'
        assert verified_transaction.transaction_id == 'test-transaction-id'
        assert verified_transaction.status == TransactionStatus.COMPLETED
    
    def test_verify_transaction_not_found(self, service):
        """Test verifying a non-existent transaction."""
        with pytest.raises(VTpassServiceError) as excinfo:
            service.verify_transaction('non-existent-reference')
        
        assert 'Transaction not found' in str(excinfo.value)