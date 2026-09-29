"""
Client module for the VTpass API.
This module provides a client for making requests to the VTpass API.
"""

import json
import time
import uuid
import hashlib
import requests
from urllib.parse import urljoin
from dataclasses import dataclass
from typing import Dict, List, Optional, Union, Any

from django.utils.translation import gettext_lazy as _

from vtpass.settings import vtpass_settings
from vtpass.exceptions import (
    VTpassAPIError, VTpassNetworkError, VTpassAuthenticationError, 
    VTpassValidationError
)
from vtpass.logger import log_api_request, log_api_response, log_error
from vtpass.constants import ResponseCode


@dataclass
class VTpassResponse:
    """
    Data class for VTpass API responses.
    This class parses and normalizes responses from the VTpass API.
    """
    success: bool
    message: str
    code: str
    data: Optional[Dict[str, Any]] = None
    transaction_id: Optional[str] = None
    reference: Optional[str] = None
    amount: Optional[Union[int, float]] = None
    response_object: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_api_response(cls, response_data: Dict[str, Any]) -> 'VTpassResponse':
        """
        Create a VTpassResponse instance from the API response data.
        
        Args:
            response_data (dict): The API response data
            
        Returns:
            VTpassResponse: A normalized response object
        """
        # Extract standard fields
        code = response_data.get('code', '')
        success = code == ResponseCode.SUCCESS
        message = response_data.get('response_description', '')
        
        # Extract transaction details
        data = response_data.get('content', {})
        if not data and 'data' in response_data:
            data = response_data.get('data', {})
            
        # Extract transaction ID
        transaction_id = None
        if isinstance(data, dict):
            transaction_id = data.get('transactions', {}).get('transactionId')
            if not transaction_id:
                # Try alternate field names
                transaction_id = (
                    data.get('transactionId') or 
                    data.get('transaction_id') or 
                    data.get('requestId')
                )
        
        # Extract reference
        reference = None
        if isinstance(data, dict):
            reference = (
                data.get('requestId') or 
                data.get('request_id') or 
                data.get('reference')
            )
            
        # Extract amount
        amount = None
        if isinstance(data, dict):
            amount_field = data.get('amount')
            if amount_field:
                try:
                    amount = float(amount_field)
                except (ValueError, TypeError):
                    amount = None
        
        return cls(
            success=success,
            message=message,
            code=code,
            data=data,
            transaction_id=transaction_id,
            reference=reference,
            amount=amount,
            response_object=response_data,
        )


class VTpassClient:
    """
    Client for making requests to the VTpass API.
    
    This class provides methods for making requests to different
    VTpass API endpoints with proper authentication and error handling.
    """
    def __init__(self, api_key=None, secret_key=None, environment=None):
        """
        Initialize the VTpass client.
        
        Args:
            api_key (str, optional): The VTpass API key
            secret_key (str, optional): The VTpass secret key
            environment (str, optional): The environment ('development' or 'production')
        """
        self.api_key = api_key or vtpass_settings.API_KEY
        self.secret_key = secret_key or vtpass_settings.SECRET_KEY
        self.environment = environment or vtpass_settings.ENVIRONMENT
        self.base_url = vtpass_settings.base_url
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """
        Create a requests session with retry configuration.
        
        Returns:
            requests.Session: The configured session
        """
        session = requests.Session()
        
        # Configure session
        session.verify = vtpass_settings.VERIFY_SSL
        
        # Set default headers
        session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })
        
        return session
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """
        Get the authentication headers for the API request.
        
        Returns:
            dict: The authentication headers
        """
        return {
            'api-key': self.api_key,
            'secret-key': self.secret_key,
            'Public-Key': self.api_key,  # Some endpoints use different header names
        }
    
    def _build_url(self, endpoint: str) -> str:
        """
        Build the full URL for an API endpoint.
        
        Args:
            endpoint (str): The API endpoint
            
        Returns:
            str: The full URL
        """
        return urljoin(self.base_url, endpoint)
    
    def _generate_request_id(self) -> str:
        """
        Generate a unique request ID.
        
        Returns:
            str: The generated request ID
        """
        return hashlib.md5(f"{uuid.uuid4()}{time.time()}".encode()).hexdigest()
    
    def _handle_response(self, response: requests.Response, endpoint: str, method: str) -> VTpassResponse:
        """
        Handle the API response.
        
        Args:
            response (requests.Response): The API response
            endpoint (str): The API endpoint
            method (str): The HTTP method
            
        Returns:
            VTpassResponse: The parsed response
            
        Raises:
            VTpassAPIError: If the API returns an error
            VTpassAuthenticationError: If there's an authentication error
        """
        log_api_response(endpoint, method, response.status_code, response.text)
        
        # Handle HTTP errors
        try:
            response.raise_for_status()
        except requests.HTTPError as e:
            if response.status_code == 401:
                raise VTpassAuthenticationError(
                    _("Authentication failed with VTpass API"),
                    status_code=response.status_code,
                    response=response.text
                ) from e
            
            raise VTpassAPIError(
                _("HTTP error: {0}").format(response.status_code),
                status_code=response.status_code,
                response=response.text
            ) from e
        
        # Parse JSON response
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            raise VTpassAPIError(
                _("Invalid JSON response from VTpass API"),
                status_code=response.status_code,
                response=response.text
            ) from e
        
        # Create a normalized response object
        vtpass_response = VTpassResponse.from_api_response(response_data)
        
        # Handle API errors
        if not vtpass_response.success and vtpass_response.code != ResponseCode.PENDING:
            error_message = vtpass_response.message or _("Unknown API error")
            raise VTpassAPIError(
                error_message,
                status_code=response.status_code,
                response=response_data
            )
        
        return vtpass_response
    
    def request(
        self, endpoint: str, method: str = 'GET', 
        data: Optional[Dict[str, Any]] = None, 
        params: Optional[Dict[str, Any]] = None
    ) -> VTpassResponse:
        """
        Make a request to the VTpass API.
        
        Args:
            endpoint (str): The API endpoint
            method (str, optional): The HTTP method. Defaults to 'GET'.
            data (dict, optional): The request data. Defaults to None.
            params (dict, optional): The query parameters. Defaults to None.
            
        Returns:
            VTpassResponse: The parsed response
            
        Raises:
            VTpassNetworkError: If there's a network error
            VTpassAPIError: If the API returns an error
        """
        url = self._build_url(endpoint)
        headers = self._get_auth_headers()
        
        # Convert empty values to None
        if data:
            data = {k: v if v != '' else None for k, v in data.items()}
        
        # Log the request
        log_api_request(endpoint, method, data, params)
        
        try:
            # Make the request
            if method.upper() == 'GET':
                response = self.session.get(
                    url, params=params, headers=headers, 
                    timeout=vtpass_settings.TIMEOUT
                )
            elif method.upper() == 'POST':
                response = self.session.post(
                    url, json=data, params=params, headers=headers, 
                    timeout=vtpass_settings.TIMEOUT
                )
            else:
                raise ValueError(_("Unsupported HTTP method: {0}").format(method))
            
            return self._handle_response(response, endpoint, method)
            
        except requests.RequestException as e:
            log_error(e, {"url": url, "method": method, "data": data, "params": params})
            raise VTpassNetworkError(
                _("Network error: {0}").format(str(e)), 
                original_error=e
            ) from e
    
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> VTpassResponse:
        """
        Make a GET request to the VTpass API.
        
        Args:
            endpoint (str): The API endpoint
            params (dict, optional): The query parameters. Defaults to None.
            
        Returns:
            VTpassResponse: The parsed response
        """
        return self.request(endpoint, method='GET', params=params)
    
    def post(
        self, endpoint: str, data: Optional[Dict[str, Any]] = None, 
        params: Optional[Dict[str, Any]] = None
    ) -> VTpassResponse:
        """
        Make a POST request to the VTpass API.
        
        Args:
            endpoint (str): The API endpoint
            data (dict, optional): The request data. Defaults to None.
            params (dict, optional): The query parameters. Defaults to None.
            
        Returns:
            VTpassResponse: The parsed response
        """
        return self.request(endpoint, method='POST', data=data, params=params)
    
    # Specific API endpoints
    def get_balance(self) -> VTpassResponse:
        """
        Get the merchant balance.
        
        Returns:
            VTpassResponse: The merchant balance response
        """
        from vtpass.constants import Endpoints
        return self.get(Endpoints.BALANCE)
    
    def get_service_categories(self) -> VTpassResponse:
        """
        Get the service categories.
        
        Returns:
            VTpassResponse: The service categories response
        """
        from vtpass.constants import Endpoints
        return self.get(Endpoints.SERVICE_CATEGORIES)
    
    def get_service_variations(self, service_id: str) -> VTpassResponse:
        """
        Get the service variations for a specific service.
        
        Args:
            service_id (str): The service ID
            
        Returns:
            VTpassResponse: The service variations response
        """
        from vtpass.constants import Endpoints
        return self.get(Endpoints.SERVICE_VARIATIONS, params={'serviceID': service_id})
    
    def verify_transaction(self, request_id: str) -> VTpassResponse:
        """
        Verify a transaction.
        
        Args:
            request_id (str): The request ID
            
        Returns:
            VTpassResponse: The transaction verification response
        """
        from vtpass.constants import Endpoints
        return self.post(Endpoints.VERIFY_TRANSACTION, data={'request_id': request_id})
    
    def verify_meter(
        self, meter_number: str, service_id: str, 
        meter_type: Optional[str] = None
    ) -> VTpassResponse:
        """
        Verify an electricity meter.
        
        Args:
            meter_number (str): The meter number
            service_id (str): The service ID
            meter_type (str, optional): The meter type ('prepaid' or 'postpaid')
            
        Returns:
            VTpassResponse: The meter verification response
        """
        from vtpass.constants import Endpoints
        data = {
            'billersCode': meter_number,
            'serviceID': service_id,
        }
        
        if meter_type:
            data['type'] = meter_type
            
        return self.post(Endpoints.VERIFY_METER, data=data)
    
    def verify_smartcard(self, smartcard_number: str, service_id: str) -> VTpassResponse:
        """
        Verify a cable TV smartcard number.
        
        Args:
            smartcard_number (str): The smartcard number
            service_id (str): The service ID
            
        Returns:
            VTpassResponse: The smartcard verification response
        """
        from vtpass.constants import Endpoints
        return self.post(
            Endpoints.VERIFY_SMARTCARD, 
            data={'billersCode': smartcard_number, 'serviceID': service_id}
        )
    
    def purchase(
        self, service_id: str, amount: Union[int, float], 
        phone: str, reference: Optional[str] = None,
        variation_code: Optional[str] = None, 
        customer_data: Optional[Dict[str, Any]] = None
    ) -> VTpassResponse:
        """
        Make a purchase.
        
        Args:
            service_id (str): The service ID
            amount (int, float): The amount
            phone (str): The phone number
            reference (str, optional): The reference. Defaults to auto-generated.
            variation_code (str, optional): The variation code. Defaults to None.
            customer_data (dict, optional): Additional customer data. Defaults to None.
            
        Returns:
            VTpassResponse: The purchase response
        """
        from vtpass.constants import Endpoints
        
        # Generate a reference if not provided
        if not reference:
            reference = self._generate_request_id()
            
        data = {
            'serviceID': service_id,
            'amount': str(amount),
            'phone': phone,
            'request_id': reference,
        }
        
        if variation_code:
            data['variation_code'] = variation_code
            
        if customer_data:
            for key, value in customer_data.items():
                data[key] = value
                
        return self.post(Endpoints.PURCHASE, data=data)