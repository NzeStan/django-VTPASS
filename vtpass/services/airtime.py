"""
Airtime service module for the VTpass package.
This module provides services for airtime top-up.
"""

from typing import Dict, List, Optional, Union, Any
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from vtpass.services.base import BaseService
from vtpass.client import VTpassClient, VTpassResponse
from vtpass.models.transaction import Transaction
from vtpass.models.service import Service
from vtpass.exceptions import VTpassValidationError, VTpassServiceError
from vtpass.constants import ServiceType, Endpoints, NetworkProvider


class AirtimeService(BaseService):
    """
    Service for airtime top-up.
    Provides methods for purchasing airtime for different network providers.
    """
    service_type = ServiceType.AIRTIME
    
    # Validation rules specific to airtime
    validation_rules = {
        'amount': {
            'required': True,
            'min_value': 50,  # Minimum airtime amount
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
        'reference': {
            'required': False,
            'min_length': 1,
            'max_length': 100,
            'type': str,
        },
    }
    
    def get_providers(self) -> List[Dict[str, str]]:
        """
        Get a list of available network providers.
        
        Returns:
            list: A list of provider dictionaries with 'id' and 'name' keys
        """
        return [
            {'id': provider[0], 'name': provider[1]} 
            for provider in NetworkProvider.CHOICES
        ]
    
    def get_service_id_for_provider(self, provider: str) -> str:
        """
        Get the service ID for a network provider.
        
        Args:
            provider (str): The provider code (e.g., 'mtn', 'airtel')
            
        Returns:
            str: The service ID for the provider
            
        Raises:
            VTpassServiceError: If the provider is not supported
        """
        # Map of provider codes to service IDs
        provider_map = {
            NetworkProvider.MTN: 'mtn',
            NetworkProvider.AIRTEL: 'airtel',
            NetworkProvider.GLO: 'glo',
            NetworkProvider.ETISALAT: 'etisalat',
        }
        
        if provider not in provider_map:
            raise VTpassServiceError(
                _("Unsupported network provider: {0}").format(provider)
            )
            
        return provider_map[provider]
    
    def validate_purchase_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data for airtime purchase.
        
        Args:
            data (dict): The purchase data
            
        Returns:
            dict: The validated data
            
        Raises:
            VTpassValidationError: If validation fails
        """
        # Validate using base rules
        validated_data = self.validate_data(data)
        
        # Additional validation specific to airtime
        provider = validated_data.get('provider')
        if provider and provider not in [p[0] for p in NetworkProvider.CHOICES]:
            raise VTpassValidationError(
                _("Invalid provider."),
                errors={'provider': [_("Provider not supported.")]}
            )
        
        return validated_data
    
    @transaction.atomic
    def purchase(
        self, phone: str, amount: float, provider: str, 
        reference: Optional[str] = None, user=None, 
        email: Optional[str] = None, callback_url: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Purchase airtime.
        
        Args:
            phone (str): The phone number to recharge
            amount (float): The amount to purchase
            provider (str): The network provider code
            reference (str, optional): The transaction reference. Defaults to auto-generated.
            user (User, optional): The user who initiated the transaction. Defaults to None.
            email (str, optional): The email address. Defaults to None.
            callback_url (str, optional): The callback URL. Defaults to None.
            meta_data (dict, optional): Additional transaction metadata. Defaults to None.
            
        Returns:
            Transaction: The created transaction
            
        Raises:
            VTpassValidationError: If validation fails
            VTpassServiceError: If the purchase fails
        """
        # Validate the data
        validated_data = self.validate_purchase_data({
            'phone': phone,
            'amount': amount,
            'provider': provider,
            'reference': reference,
        })
        
        # Get the service ID for the provider
        service_id = self.get_service_id_for_provider(provider)
        
        # Get or create the service
        service = self.get_service_by_id(service_id)
        if not service:
            # Get from provider to update service cache
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
            callback_url=callback_url,
            meta_data=meta_data or {},
        )
        
        try:
            # Make the API request to purchase airtime
            response = self.client.purchase(
                service_id=service_id,
                amount=amount,
                phone=phone,
                reference=reference,
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
                _("Airtime purchase failed: {0}").format(str(e))
            ) from e
    
    def verify_transaction(self, reference: str) -> Transaction:
        """
        Verify an airtime transaction.
        
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