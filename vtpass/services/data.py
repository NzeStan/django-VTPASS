"""
Data service module for the VTpass package.
This module provides services for mobile data subscriptions.
"""

from typing import Dict, List, Optional, Union, Any
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from vtpass.services.base import BaseService
from vtpass.client import VTpassClient, VTpassResponse
from vtpass.models.transaction import Transaction
from vtpass.models.service import Service, ServiceVariation
from vtpass.exceptions import VTpassValidationError, VTpassServiceError
from vtpass.constants import ServiceType, Endpoints, NetworkProvider


class DataService(BaseService):
    """
    Service for mobile data subscriptions.
    Provides methods for purchasing data plans for different network providers.
    """
    service_type = ServiceType.DATA
    
    # Validation rules specific to data subscriptions
    validation_rules = {
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
        'plan': {
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
            NetworkProvider.MTN: 'mtn-data',
            NetworkProvider.AIRTEL: 'airtel-data',
            NetworkProvider.GLO: 'glo-data',
            NetworkProvider.ETISALAT: 'etisalat-data',
        }
        
        if provider not in provider_map:
            raise VTpassServiceError(
                _("Unsupported network provider: {0}").format(provider)
            )
            
        return provider_map[provider]
    
    def get_data_plans(self, provider: str) -> List[Dict[str, Any]]:
        """
        Get a list of data plans for a provider.
        
        Args:
            provider (str): The provider code
            
        Returns:
            list: A list of data plan dictionaries
            
        Raises:
            VTpassServiceError: If the provider is not supported or if fetching plans fails
        """
        service_id = self.get_service_id_for_provider(provider)
        
        try:
            # Get the data plans from the API
            response = self.client.get_service_variations(service_id)
            
            if not response.success:
                raise VTpassServiceError(
                    _("Failed to fetch data plans: {0}").format(response.message)
                )
                
            # Parse the response
            content = response.data
            variations = content.get('varations') or content.get('variations') or []
            
            # Format the plans
            plans = []
            for variation in variations:
                plan = {
                    'code': variation.get('variation_code'),
                    'name': variation.get('name'),
                    'amount': variation.get('variation_amount'),
                    'description': variation.get('variation_desc') or '',
                }
                plans.append(plan)
                
            return plans
        except Exception as e:
            raise VTpassServiceError(
                _("Error fetching data plans: {0}").format(str(e))
            ) from e
    
    def validate_purchase_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data for data plan purchase.
        
        Args:
            data (dict): The purchase data
            
        Returns:
            dict: The validated data
            
        Raises:
            VTpassValidationError: If validation fails
        """
        # Validate using base rules
        validated_data = self.validate_data(data)
        
        # Additional validation specific to data plans
        provider = validated_data.get('provider')
        if provider and provider not in [p[0] for p in NetworkProvider.CHOICES]:
            raise VTpassValidationError(
                _("Invalid provider."),
                errors={'provider': [_("Provider not supported.")]}
            )
        
        return validated_data
    
    @transaction.atomic
    def purchase(
        self, phone: str, provider: str, plan: str,
        reference: Optional[str] = None, user=None, 
        email: Optional[str] = None, callback_url: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Purchase a data plan.
        
        Args:
            phone (str): The phone number to subscribe
            provider (str): The network provider code
            plan (str): The plan variation code
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
            'provider': provider,
            'plan': plan,
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
        
        # Get the variation
        variation = self.get_variation_by_code(service, plan)
        if not variation:
            # Try to fetch variations from API
            try:
                # Fetch variations from API to update cache
                self.get_data_plans(provider)
                variation = self.get_variation_by_code(service, plan)
                if not variation:
                    raise VTpassServiceError(
                        _("Plan not found: {0}").format(plan)
                    )
            except Exception as e:
                raise VTpassServiceError(
                    _("Error fetching plan information: {0}").format(str(e))
                ) from e
        
        # Generate a reference if not provided
        if not reference:
            reference = self.generate_reference()
            
        # Create the transaction record
        transaction = self.create_transaction(
            service=service,
            amount=variation.amount,
            phone=phone,
            reference=reference,
            variation=variation,
            user=user,
            email=email,
            callback_url=callback_url,
            meta_data=meta_data or {},
        )
        
        try:
            # Make the API request to purchase data plan
            response = self.client.purchase(
                service_id=service_id,
                amount=variation.amount,
                phone=phone,
                reference=reference,
                variation_code=plan,
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
                _("Data plan purchase failed: {0}").format(str(e))
            ) from e
    
    def verify_transaction(self, reference: str) -> Transaction:
        """
        Verify a data plan transaction.
        
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