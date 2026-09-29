"""
Tests for the VTpass client.
This module provides tests for the VTpass client.
"""

import pytest
import json
import responses
from decimal import Decimal

from vtpass.client import VTpassClient, VTpassResponse
from vtpass.constants import Endpoints, ResponseCode
from vtpass.exceptions import VTpassAPIError, VTpassAuthenticationError, VTpassNetworkError


@pytest.fixture
def client():
    """Create a test client."""
    return VTpassClient(
        api_key='test-api-key',
        secret_key='test-secret-key',
        environment='development'
    )


@pytest.fixture
def mock_response():
    """Create a mock response."""
    return {
        'code': ResponseCode.SUCCESS,
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


class TestVTpassResponse:
    """Tests for the VTpassResponse class."""
    
    def test_from_api_response_success(self, mock_response):
        """Test creating a response from a successful API response."""
        response = VTpassResponse.from_api_response(mock_response)
        
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
        assert response.transaction_id == 'test-transaction-id'
        assert response.reference == 'test-request-id'
        assert response.data == mock_response['content']
        assert response.response_object == mock_response
    
    def test_from_api_response_failure(self):
        """Test creating a response from a failed API response."""
        mock_data = {
            'code': ResponseCode.FAILED,
            'response_description': 'Failed',
            'requestId': 'test-request-id',
            'content': {}
        }
        
        response = VTpassResponse.from_api_response(mock_data)
        
        assert response.success is False
        assert response.message == 'Failed'
        assert response.code == ResponseCode.FAILED
        assert response.transaction_id is None
        assert response.reference == 'test-request-id'
        assert response.data == {}
        assert response.response_object == mock_data


class TestVTpassClient:
    """Tests for the VTpassClient class."""
    
    def test_init(self, client):
        """Test initializing the client."""
        assert client.api_key == 'test-api-key'
        assert client.secret_key == 'test-secret-key'
        assert client.environment == 'development'
        assert client.base_url == 'https://sandbox.vtpass.com/api'
        assert client.session is not None
    
    def test_get_auth_headers(self, client):
        """Test getting authentication headers."""
        headers = client._get_auth_headers()
        
        assert headers['api-key'] == 'test-api-key'
        assert headers['secret-key'] == 'test-secret-key'
        assert headers['Public-Key'] == 'test-api-key'
    
    def test_build_url(self, client):
        """Test building a URL."""
        url = client._build_url('test-endpoint')
        
        assert url == 'https://sandbox.vtpass.com/api/test-endpoint'
    
    def test_generate_request_id(self, client):
        """Test generating a request ID."""
        request_id = client._generate_request_id()
        
        assert isinstance(request_id, str)
        assert len(request_id) == 32  # MD5 hash length
    
    @responses.activate
    def test_request_get_success(self, client, mock_response):
        """Test making a successful GET request."""
        # Mock the API response
        responses.add(
            responses.GET,
            'https://sandbox.vtpass.com/api/test-endpoint',
            json=mock_response,
            status=200
        )
        
        # Make the request
        response = client.request('test-endpoint', method='GET')
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
        assert response.transaction_id == 'test-transaction-id'
        assert response.reference == 'test-request-id'
        assert response.data == mock_response['content']
    
    @responses.activate
    def test_request_post_success(self, client, mock_response):
        """Test making a successful POST request."""
        # Mock the API response
        responses.add(
            responses.POST,
            'https://sandbox.vtpass.com/api/test-endpoint',
            json=mock_response,
            status=200
        )
        
        # Make the request
        data = {'test': 'data'}
        response = client.request('test-endpoint', method='POST', data=data)
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
        assert response.transaction_id == 'test-transaction-id'
        assert response.reference == 'test-request-id'
        assert response.data == mock_response['content']
    
    @responses.activate
    def test_request_api_error(self, client):
        """Test handling an API error."""
        # Mock the API response
        error_response = {
            'code': ResponseCode.FAILED,
            'response_description': 'API Error',
            'requestId': 'test-request-id',
            'content': {}
        }
        
        responses.add(
            responses.GET,
            'https://sandbox.vtpass.com/api/test-endpoint',
            json=error_response,
            status=400
        )
        
        # Make the request and verify it raises an error
        with pytest.raises(VTpassAPIError) as excinfo:
            client.request('test-endpoint', method='GET')
        
        assert 'API Error' in str(excinfo.value)
    
    @responses.activate
    def test_request_auth_error(self, client):
        """Test handling an authentication error."""
        # Mock the API response
        responses.add(
            responses.GET,
            'https://sandbox.vtpass.com/api/test-endpoint',
            json={'error': 'Authentication failed'},
            status=401
        )
        
        # Make the request and verify it raises an error
        with pytest.raises(VTpassAuthenticationError) as excinfo:
            client.request('test-endpoint', method='GET')
        
        assert 'Authentication failed' in str(excinfo.value)
    
    @responses.activate
    def test_request_network_error(self, client):
        """Test handling a network error."""
        # Mock a network error
        responses.add(
            responses.GET,
            'https://sandbox.vtpass.com/api/test-endpoint',
            body=responses.ConnectionError('Network error')
        )
        
        # Make the request and verify it raises an error
        with pytest.raises(VTpassNetworkError) as excinfo:
            client.request('test-endpoint', method='GET')
        
        assert 'Network error' in str(excinfo.value)
    
    @responses.activate
    def test_get_balance(self, client, mock_response):
        """Test getting the merchant balance."""
        # Mock the API response
        responses.add(
            responses.GET,
            f'https://sandbox.vtpass.com/api/{Endpoints.BALANCE}',
            json=mock_response,
            status=200
        )
        
        # Make the request
        response = client.get_balance()
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
    
    @responses.activate
    def test_get_service_categories(self, client, mock_response):
        """Test getting service categories."""
        # Mock the API response
        responses.add(
            responses.GET,
            f'https://sandbox.vtpass.com/api/{Endpoints.SERVICE_CATEGORIES}',
            json=mock_response,
            status=200
        )
        
        # Make the request
        response = client.get_service_categories()
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
    
    @responses.activate
    def test_get_service_variations(self, client, mock_response):
        """Test getting service variations."""
        # Mock the API response
        responses.add(
            responses.GET,
            f'https://sandbox.vtpass.com/api/{Endpoints.SERVICE_VARIATIONS}',
            json=mock_response,
            status=200
        )
        
        # Make the request
        response = client.get_service_variations('mtn-data')
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
    
    @responses.activate
    def test_verify_transaction(self, client, mock_response):
        """Test verifying a transaction."""
        # Mock the API response
        responses.add(
            responses.POST,
            f'https://sandbox.vtpass.com/api/{Endpoints.VERIFY_TRANSACTION}',
            json=mock_response,
            status=200
        )
        
        # Make the request
        response = client.verify_transaction('test-request-id')
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
    
    @responses.activate
    def test_verify_meter(self, client, mock_response):
        """Test verifying a meter."""
        # Mock the API response
        responses.add(
            responses.POST,
            f'https://sandbox.vtpass.com/api/{Endpoints.VERIFY_METER}',
            json=mock_response,
            status=200
        )
        
        # Make the request
        response = client.verify_meter(
            meter_number='12345678',
            service_id='ikeja-electric',
            meter_type='prepaid'
        )
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
    
    @responses.activate
    def test_verify_smartcard(self, client, mock_response):
        """Test verifying a smartcard."""
        # Mock the API response
        responses.add(
            responses.POST,
            f'https://sandbox.vtpass.com/api/{Endpoints.VERIFY_SMARTCARD}',
            json=mock_response,
            status=200
        )
        
        # Make the request
        response = client.verify_smartcard(
            smartcard_number='12345678',
            service_id='dstv'
        )
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
    
    @responses.activate
    def test_purchase(self, client, mock_response):
        """Test making a purchase."""
        # Mock the API response
        responses.add(
            responses.POST,
            f'https://sandbox.vtpass.com/api/{Endpoints.PURCHASE}',
            json=mock_response,
            status=200
        )
        
        # Make the request
        response = client.purchase(
            service_id='mtn',
            amount=100,
            phone='08012345678',
            reference='test-reference'
        )
        
        # Verify the response
        assert response.success is True
        assert response.message == 'Success'
        assert response.code == ResponseCode.SUCCESS
        assert response.transaction_id == 'test-transaction-id'