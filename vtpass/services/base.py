"""
Base service module for VTpass package.
This module defines the BaseService class that all service classes inherit from.
"""

import uuid
from typing import Dict, List, Optional, Union, Any
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from vtpass.client import VTpassClient, VTpassResponse
from vtpass.exceptions import (
    VTpassError, VTpassAPIError, VTpassValidationError, VTpassServiceError
)
from vtpass.models.transaction import Transaction
from vtpass.models.service import Service, ServiceVariation
from vtpass.constants import TransactionStatus
from vtpass.logger import logger
from vtpass.settings import vtpass_settings


class BaseService:
    """
    Base service class for VTpass services.
    All service classes inherit from this class and implement service-specific methods.
    """
    # Service type from ServiceType constants
    service_type = None
    
    # Default validation rules
    validation_rules = {
        'amount': {
            'required': True,
            'min_value': 0,
            'type': float,
        },
        'phone': {
            'required': True,
            'min_length': 10,
            'max_length': 15,
            'type': str,
        },
        'reference': {
            'required': False,
            'min_length': 1,
            'max_length': 100,
            'type': str,
        },
    }
    
    def __init__(self, client=None):
        """
        Initialize the service.
        
        Args:
            client (VTpassClient, optional): The VTpass client. Defaults to None.
        """
        self.client = client or VTpassClient()
        
        if not self.service_type:
            raise NotImplementedError(
                "Service classes must define a service_type attribute."
            )
    
    def validate_data(self, data: Dict[str, Any], rules: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Validate the data against the rules.
        
        Args:
            data (dict): The data to validate
            rules (dict, optional): The validation rules. Defaults to self.validation_rules.
            
        Returns:
            dict: The validated data
            
        Raises:
            VTpassValidationError: If validation fails
        """
        rules = rules or self.validation_rules
        errors = {}
        validated_data = {}
        
        for field, field_rules in rules.items():
            value = data.get(field)
            field_errors = []
            
            # Check if required
            if field_rules.get('required', False) and value is None:
                field_errors.append(_("This field is required."))
                errors[field] = field_errors
                continue
                
            # Skip further validation if not required and value is None
            if not field_rules.get('required', False) and value is None:
                validated_data[field] = None
                continue
                
            # Check type
            field_type = field_rules.get('type')
            if field_type and not isinstance(value, field_type):
                try:
                    # Try to convert
                    value = field_type(value)
                except (ValueError, TypeError):
                    field_errors.append(
                        _("This field must be of type {0}.").format(field_type.__name__)
                    )
            
            # Check min value
            min_value = field_rules.get('min_value')
            if min_value is not None and value < min_value:
                field_errors.append(
                    _("This field must be greater than or equal to {0}.").format(min_value)
                )
            
            # Check max value
            max_value = field_rules.get('max_value')
            if max_value is not None and value > max_value:
                field_errors.append(
                    _("This field must be less than or equal to {0}.").format(max_value)
                )
            
            # Check min length
            min_length = field_rules.get('min_length')
            if min_length is not None and isinstance(value, (str, list, dict)) and len(value) < min_length:
                field_errors.append(
                    _("This field must have at least {0} characters.").format(min_length)
                )
            
            # Check max length
            max_length = field_rules.get('max_length')
            if max_length is not None and isinstance(value, (str, list, dict)) and len(value) > max_length:
                field_errors.append(
                    _("This field must have at most {0} characters.").format(max_length)
                )
            
            # Add errors if any
            if field_errors:
                errors[field] = field_errors
            else:
                validated_data[field] = value
        
        # Raise validation error if there are errors
        if errors:
            raise VTpassValidationError(
                _("Validation error."),
                errors=errors
            )
        
        return validated_data
    
    def get_services(self) -> List[Service]:
        """
        Get all services for this service type.
        
        Returns:
            list: A list of Service instances
        """
        return Service.get_services_by_type(self.service_type)
    
    def get_service_by_id(self, service_id: str) -> Optional[Service]:
        """
        Get a service by its ID.
        
        Args:
            service_id (str): The service ID
            
        Returns:
            Service: The Service instance or None if not found
        """
        return Service.get_by_service_id(service_id)
    
    def get_service_variations(self, service: Service) -> List[ServiceVariation]:
        """
        Get all variations for a service.
        
        Args:
            service (Service): The service instance
            
        Returns:
            list: A list of ServiceVariation instances
        """
        return service.get_variations()
    
    def get_variation_by_code(self, service: Service, variation_code: str) -> Optional[ServiceVariation]:
        """
        Get a variation by its code.
        
        Args:
            service (Service): The service instance
            variation_code (str): The variation code
            
        Returns:
            ServiceVariation: The ServiceVariation instance or None if not found
        """
        return ServiceVariation.get_by_code(service, variation_code)
    
    def fetch_from_api(self, endpoint: str, method: str = 'GET', **kwargs) -> VTpassResponse:
        """
        Fetch data from the VTpass API.
        
        Args:
            endpoint (str): The API endpoint
            method (str, optional): The HTTP method. Defaults to 'GET'.
            **kwargs: Additional arguments to pass to the request
            
        Returns:
            VTpassResponse: The API response
        """
        if method.upper() == 'GET':
            return self.client.get(endpoint, params=kwargs.get('params'))
        else:
            return self.client.post(
                endpoint, 
                data=kwargs.get('data'), 
                params=kwargs.get('params')
            )
    
    @transaction.atomic
    def create_transaction(
        self, service: Service, amount: float, phone: str, 
        reference: Optional[str] = None, variation: Optional[ServiceVariation] = None,
        user=None, email: Optional[str] = None, customer_data: Optional[Dict[str, Any]] = None,
        verification_code: Optional[str] = None, callback_url: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Create a transaction record.
        
        Args:
            service (Service): The service instance
            amount (float): The transaction amount
            phone (str): The phone number
            reference (str, optional): The transaction reference. Defaults to auto-generated.
            variation (ServiceVariation, optional): The service variation. Defaults to None.
            user (User, optional): The user who initiated the transaction. Defaults to None.
            email (str, optional): The email address. Defaults to None.
            customer_data (dict, optional): Additional customer data. Defaults to None.
            verification_code (str, optional): The verification code. Defaults to None.
            callback_url (str, optional): The callback URL. Defaults to None.
            meta_data (dict, optional): Additional transaction metadata. Defaults to None.
            
        Returns:
            Transaction: The created transaction
        """
        # Generate a reference if not provided
        if not reference:
            reference = self.generate_reference()
            
        # Create the transaction
        transaction = Transaction.objects.create(
            service=service,
            service_type=service.service_type,
            service_variation=variation,
            amount=amount,
            phone=phone,
            reference=reference,
            user=user,
            email=email or '',
            customer_data=customer_data or {},
            verification_code=verification_code or '',
            status=TransactionStatus.PENDING,
            callback_url=callback_url or '',
            meta_data=meta_data or {},
        )
        
        return transaction
    
    def update_transaction_from_response(
        self, transaction: Transaction, response: VTpassResponse
    ) -> Transaction:
        """
        Update a transaction from an API response.
        
        Args:
            transaction (Transaction): The transaction to update
            response (VTpassResponse): The API response
            
        Returns:
            Transaction: The updated transaction
        """
        # Update status based on response code
        from vtpass.constants import ResponseCode
        
        status_map = ResponseCode.STATUS_MAP
        transaction.status = status_map.get(response.code, transaction.status)
        
        # Update transaction ID if available
        if response.transaction_id:
            transaction.transaction_id = response.transaction_id
            
        # Update response data
        transaction.response_data = response.response_object or {}
        transaction.response_message = response.message
        
        # Save the transaction
        transaction.save()
        
        return transaction
    
    def generate_reference(self) -> str:
        """
        Generate a unique reference.
        
        Returns:
            str: The generated reference
        """
        return f"vtpass-{uuid.uuid4().hex[:12]}"
    
    def check_transaction_status(self, transaction: Transaction) -> Transaction:
        """
        Check the status of a transaction.
        
        Args:
            transaction (Transaction): The transaction to check
            
        Returns:
            Transaction: The updated transaction
        """
        # If transaction is already completed or failed, just return it
        if transaction.is_completed or transaction.is_failed:
            return transaction
            
        try:
            # Query the API for the transaction status
            from vtpass.constants import Endpoints
            response = self.client.verify_transaction(transaction.reference)
            
            # Update the transaction
            return self.update_transaction_from_response(transaction, response)
        except Exception as e:
            logger.error(f"Error checking transaction status: {str(e)}")
            return transaction