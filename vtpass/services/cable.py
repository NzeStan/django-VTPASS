"""
Cable TV service module for the VTpass package.
This module provides services for cable TV subscriptions.
"""

from typing import Dict, List, Optional, Union, Any
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from vtpass.services.base import BaseService
from vtpass.client import VTpassClient, VTpassResponse
from vtpass.models.transaction import Transaction
from vtpass.models.service import Service, ServiceVariation
from vtpass.exceptions import VTpassValidationError, VTpassServiceError
from vtpass.constants import ServiceType, Endpoints, CableTVProvider


class CableTVService(BaseService):
    """
    Service for cable TV subscriptions.
    Provides methods for paying cable TV subscriptions for different providers.
    """
    service_type = ServiceType.CABLE_TV
    
    # Validation rules specific to cable TV subscriptions
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
        'smartcard_number': {
            'required': True,
            'min_length': 5,
            'max_length': 20,
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
        Get a list of available cable TV providers.
        
        Returns:
            list: A list of provider dictionaries with 'id' and 'name' keys
        """
        return [
            {'id': provider[0], 'name': provider[1]} 
            for provider in CableTVProvider.CHOICES
        ]
    
    def get_service_id_for_provider(self, provider: str) -> str:
        """
        Get the service ID for a cable TV provider.
        
        Args:
            provider (str): The provider code (e.g., 'dstv', 'gotv')
            
        Returns:
            str: The service ID for the provider
            
        Raises:
            VTpassServiceError: If the provider is not supported
        """
        if provider not in CableTVProvider.CODES:
            raise VTpassServiceError(
                _("Unsupported cable TV provider: {0}").format(provider)
            )
            
        return CableTVProvider.CODES[provider]
    
    def get_plans(self, provider: str) -> List[Dict[str, Any]]:
        """
        Get a list of subscription plans for a provider.
        
        Args:
            provider (str): The provider code
            
        Returns:
            list: A list of plan dictionaries
            
        Raises:
            VTpassServiceError: If the provider is not supported or if fetching plans fails
        """
        service_id = self.get_service_id_for_provider(provider)
        
        try:
            # Get the plans from the API
            response = self.client.get_service_variations(service_id)
            
            if not response.success:
                raise VTpassServiceError(
                    _("Failed to fetch plans: {0}").format(response.message)
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
                _("Error fetching plans: {0}").format(str(e))
            ) from e
    
    def validate_purchase_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data for cable TV subscription.
        
        Args:
            data (dict): The purchase data
            
        Returns:
            dict: The validated data
            
        Raises:
            VTpassValidationError: If validation fails
        """
        # Validate using base rules
        validated_data = self.validate_data(data)
        
        # Additional validation specific to cable TV
        provider = validated_data.get('provider')
        if provider and provider not in [p[0] for p in CableTVProvider.CHOICES]:
            raise VTpassValidationError(
                _("Invalid provider."),
                errors={'provider': [_("Provider not supported.")]}
            )
        
        return validated_data
    
    def verify_smartcard(
        self, smartcard_number: str, provider: str
    ) -> Dict[str, Any]:
        """
        Verify a smartcard number.
        
        Args:
            smartcard_number (str): The smartcard number to verify
            provider (str): The cable TV provider code
            
        Returns:
            dict: The verified smartcard information
            
        Raises:
            VTpassServiceError: If the verification fails
        """
        service_id = self.get_service_id_for_provider(provider)
        
        try:
            # Verify the smartcard through the API
            response = self.client.verify_smartcard(
                smartcard_number=smartcard_number, 
                service_id=service_id
            )
            
            if not response.success:
                raise VTpassServiceError(
                    _("Smartcard verification failed: {0}").format(response.message)
                )
                
            # Parse the response
            content = response.data
            
            # Format the verification result
            result = {
                'customer_name': content.get('Customer_Name') or content.get('name'),
                'smartcard_number': content.get('smartcard_number') or smartcard_number,
                'provider': provider,
                'verified': True,
            }
                
            return result
        except Exception as e:
            raise VTpassServiceError(
                _("Error verifying smartcard: {0}").format(str(e))
            ) from e
    
    @transaction.atomic
    def purchase(
        self, smartcard_number: str, provider: str, plan: str, phone: str,
        reference: Optional[str] = None, user=None, 
        email: Optional[str] = None, callback_url: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Pay for a cable TV subscription.
        
        Args:
            smartcard_number (str): The smartcard number
            provider (str): The cable TV provider code
            plan (str): The subscription plan code
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
            'smartcard_number': smartcard_number,
            'provider': provider,
            'plan': plan,
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
        
        # Get the variation
        variation = self.get_variation_by_code(service, plan)
        if not variation:
            # Try to fetch variations from API
            try:
                # Fetch variations from API to update cache
                self.get_plans(provider)
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
            verification_code=smartcard_number,
            callback_url=callback_url,
            customer_data={
                'smartcard_number': smartcard_number,
            },
            meta_data=meta_data or {},
        )
        
        try:
            # Make the API request to pay for the subscription
            response = self.client.purchase(
                service_id=service_id,
                amount=variation.amount,
                phone=phone,
                reference=reference,
                variation_code=plan,
                customer_data={
                    'billersCode': smartcard_number,
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
                _("Cable TV subscription payment failed: {0}").format(str(e))
            ) from e
    
    def verify_transaction(self, reference: str) -> Transaction:
        """
        Verify a cable TV subscription transaction.
        
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