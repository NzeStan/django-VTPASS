"""
Electricity service module for the VTpass package.
This module provides services for electricity bill payments.
"""

from typing import Dict, List, Optional, Union, Any
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from vtpass.services.base import BaseService
from vtpass.client import VTpassClient, VTpassResponse
from vtpass.models.transaction import Transaction
from vtpass.models.service import Service
from vtpass.exceptions import VTpassValidationError, VTpassServiceError
from vtpass.constants import ServiceType, Endpoints, ElectricityProvider, MeterType


class ElectricityService(BaseService):
    """
    Service for electricity bill payments.
    Provides methods for paying electricity bills for different providers.
    """
    service_type = ServiceType.ELECTRICITY
    
    # Validation rules specific to electricity bills
    validation_rules = {
        'amount': {
            'required': True,
            'min_value': 500,  # Minimum electricity bill payment
            'type': float,
        },
        'phone': {
            'required': True,
            'min_length': 10,
            'max_length': 15,
            'type': str,
        },
        'provider': {
            'required': True,
            'type': str,
        },
        'meter_number': {
            'required': True,
            'min_length': 5,
            'max_length': 30,
            'type': str,
        },
        'meter_type': {
            'required': True,
            'type': str,
        },
        'reference': {
            'required': False,
            'min_length': 1,
            'max_length': 100,
            'type': str,
        },
    }
    
    def get_providers(self) -> List[Dict[str, str]]:
        """
        Get a list of available electricity providers.
        
        Returns:
            list: A list of provider dictionaries with 'id' and 'name' keys
        """
        return [
            {'id': provider[0], 'name': provider[1]} 
            for provider in ElectricityProvider.CHOICES
        ]
    
    def get_meter_types(self) -> List[Dict[str, str]]:
        """
        Get a list of available meter types.
        
        Returns:
            list: A list of meter type dictionaries with 'id' and 'name' keys
        """
        return [
            {'id': meter_type[0], 'name': meter_type[1]} 
            for meter_type in MeterType.CHOICES
        ]
    
    def get_service_id_for_provider(self, provider: str) -> str:
        """
        Get the service ID for an electricity provider.
        
        Args:
            provider (str): The provider code (e.g., 'ikedc', 'ekedc')
            
        Returns:
            str: The service ID for the provider
            
        Raises:
            VTpassServiceError: If the provider is not supported
        """
        if provider not in ElectricityProvider.CODES:
            raise VTpassServiceError(
                _("Unsupported electricity provider: {0}").format(provider)
            )
            
        return ElectricityProvider.CODES[provider]
    
    def validate_purchase_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data for electricity bill payment.
        
        Args:
            data (dict): The purchase data
            
        Returns:
            dict: The validated data
            
        Raises:
            VTpassValidationError: If validation fails
        """
        # Validate using base rules
        validated_data = self.validate_data(data)
        
        # Additional validation specific to electricity bills
        provider = validated_data.get('provider')
        if provider and provider not in [p[0] for p in ElectricityProvider.CHOICES]:
            raise VTpassValidationError(
                _("Invalid provider."),
                errors={'provider': [_("Provider not supported.")]}
            )
        
        meter_type = validated_data.get('meter_type')
        if meter_type and meter_type not in [m[0] for m in MeterType.CHOICES]:
            raise VTpassValidationError(
                _("Invalid meter type."),
                errors={'meter_type': [_("Meter type not supported.")]}
            )
        
        return validated_data
    
    def verify_meter(
        self, meter_number: str, provider: str, meter_type: str
    ) -> Dict[str, Any]:
        """
        Verify an electricity meter.
        
        Args:
            meter_number (str): The meter number to verify
            provider (str): The electricity provider code
            meter_type (str): The meter type ('prepaid' or 'postpaid')
            
        Returns:
            dict: The verified meter information
            
        Raises:
            VTpassServiceError: If the verification fails
        """
        service_id = self.get_service_id_for_provider(provider)
        
        try:
            # Verify the meter through the API
            response = self.client.verify_meter(
                meter_number=meter_number, 
                service_id=service_id,
                meter_type=meter_type
            )
            
            if not response.success:
                raise VTpassServiceError(
                    _("Meter verification failed: {0}").format(response.message)
                )
                
            # Parse the response
            content = response.data
            
            # Format the verification result
            result = {
                'customer_name': content.get('Customer_Name') or content.get('name'),
                'address': content.get('Address') or content.get('address'),
                'meter_number': content.get('Meter_Number') or meter_number,
                'provider': provider,
                'meter_type': meter_type,
                'verified': True,
            }
                
            return result
        except Exception as e:
            raise VTpassServiceError(
                _("Error verifying meter: {0}").format(str(e))
            ) from e
    
    @transaction.atomic
    def purchase(
        self, meter_number: str, amount: float, provider: str, meter_type: str,
        phone: str, reference: Optional[str] = None, user=None, 
        email: Optional[str] = None, callback_url: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Pay an electricity bill.
        
        Args:
            meter_number (str): The meter number
            amount (float): The amount to pay
            provider (str): The electricity provider code
            meter_type (str): The meter type ('prepaid' or 'postpaid')
            phone (str): The phone number
            reference (str, optional): The transaction reference. Defaults to auto-generated.
            user (User, optional): The user who initiated the transaction. Defaults to None.
            email (str, optional): The email address. Defaults to None.
            callback_url (str, optional): The callback URL. Defaults to None.
            meta_data (dict, optional): Additional transaction metadata. Defaults to None.
            
        Returns:
            Transaction: The created transaction
            
        Raises:
            VTpassValidationError: If validation fails
            VTpassServiceError: If the payment fails
        """
        # Validate the data
        validated_data = self.validate_purchase_data({
            'meter_number': meter_number,
            'amount': amount,
            'provider': provider,
            'meter_type': meter_type,
            'phone': phone,
            'reference': reference,
        })
        
        # Get the service ID for the provider
        service_id = self.get_service_id_for_provider(provider)
        
        # Get or create the service
        service = self.get_service_by_id(service_id)
        if not service:
            # Try to fetch service info from API
            try:
                self.client.get_service_categories()
                service = self.get_service_by_id(service_id)
                if not service:
                    raise VTpassServiceError(
                        _("Service not found for provider: {0}").format(provider)
                    )
            except Exception as e:
                raise VTpassServiceError(
                    _("Error fetching service information: {0}").format(str(e))
                ) from e
        
        # Generate a reference if not provided
        if not reference:
            reference = self.generate_reference()
            
        # Create the transaction record
        transaction = self.create_transaction(
            service=service,
            amount=amount,
            phone=phone,
            reference=reference,
            user=user,
            email=email,
            verification_code=meter_number,
            callback_url=callback_url,
            customer_data={
                'meter_number': meter_number,
                'meter_type': meter_type,
            },
            meta_data=meta_data or {},
        )
        
        try:
            # Make the API request to pay the electricity bill
            response = self.client.purchase(
                service_id=service_id,
                amount=amount,
                phone=phone,
                reference=reference,
                customer_data={
                    'billersCode': meter_number,
                    'type': meter_type,
                }
            )
            
            # Update the transaction with the response
            self.update_transaction_from_response(transaction, response)
            
            return transaction
        except Exception as e:
            # Update the transaction as failed
            transaction.status = 'failed'
            transaction.response_message = str(e)
            transaction.save()
            
            # Re-raise the exception
            raise VTpassServiceError(
                _("Electricity bill payment failed: {0}").format(str(e))
            ) from e
    
    def verify_transaction(self, reference: str) -> Transaction:
        """
        Verify an electricity bill payment transaction.
        
        Args:
            reference (str): The transaction reference
            
        Returns:
            Transaction: The verified transaction
            
        Raises:
            VTpassServiceError: If the transaction is not found
        """
        # Get the transaction
        transaction = Transaction.get_by_reference(reference)
        if not transaction:
            raise VTpassServiceError(
                _("Transaction not found: {0}").format(reference)
            )
            
        # Check the transaction status
        return self.check_transaction_status(transaction)