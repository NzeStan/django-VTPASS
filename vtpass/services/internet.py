"""
Internet service module for the VTpass package.
This module provides services for internet subscriptions like Smile, Spectranet, etc.
"""

from typing import Dict, List, Optional, Union, Any
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from vtpass.services.base import BaseService
from vtpass.client import VTpassClient, VTpassResponse
from vtpass.models.transaction import Transaction
from vtpass.models.service import Service, ServiceVariation
from vtpass.exceptions import VTpassValidationError, VTpassServiceError
from vtpass.constants import ServiceType, Endpoints, InternetProvider


class InternetService(BaseService):
    """
    Service for internet subscriptions.
    Provides methods for making internet subscription payments like Smile, Spectranet, etc.
    """
    service_type = ServiceType.INTERNET
    
    # Validation rules specific to internet subscriptions
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
        'account_number': {
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
        Get a list of available internet providers.
        
        Returns:
            list: A list of provider dictionaries with 'id' and 'name' keys
        """
        return [
            {'id': provider[0], 'name': provider[1]} 
            for provider in InternetProvider.CHOICES
        ]
    
    def get_service_id_for_provider(self, provider: str) -> str:
        """
        Get the service ID for an internet provider.
        
        Args:
            provider (str): The provider code (e.g., 'smile', 'spectranet')
            
        Returns:
            str: The service ID for the provider
            
        Raises:
            VTpassServiceError: If the provider is not supported
        """
        if provider not in InternetProvider.CODES:
            raise VTpassServiceError(
                _("Unsupported internet provider: {0}").format(provider)
            )
            
        return InternetProvider.CODES[provider]
    
    def get_plans(self, provider: str) -> List[Dict[str, Any]]:
        """
        Get a list of internet plans for a provider.
        
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
        Validate data for internet subscription.
        
        Args:
            data (dict): The purchase data
            
        Returns:
            dict: The validated data
            
        Raises:
            VTpassValidationError: If validation fails
        """
        # Validate using base rules
        validated_data = self.validate_data(data)
        
        # Additional validation specific to internet subscriptions
        provider = validated_data.get('provider')
        if provider and provider not in [p[0] for p in InternetProvider.CHOICES]:
            raise VTpassValidationError(
                _("Invalid provider."),
                errors={'provider': [_("Provider not supported.")]}
            )
        
        return validated_data
    
    def verify_account(
        self, account_number: str, provider: str
    ) -> Dict[str, Any]:
        """
        Verify an internet account.
        
        Args:
            account_number (str): The account number to verify
            provider (str): The internet provider code
            
        Returns:
            dict: The verified account information
            
        Raises:
            VTpassServiceError: If the verification fails
        """
        service_id = self.get_service_id_for_provider(provider)
        
        try:
            # Verify the account through the API
            # Note: For Smile, there's a specific endpoint
            if provider == InternetProvider.SMILE:
                response = self.client.post(
                    Endpoints.VERIFY_SMILE, 
                    data={
                        'billersCode': account_number, 
                        'serviceID': service_id
                    }
                )
            else:
                # For others, use customer verification
                response = self.client.post(
                    Endpoints.VERIFY_CUSTOMER, 
                    data={
                        'billersCode': account_number, 
                        'serviceID': service_id
                    }
                )
            
            if not response.success:
                raise VTpassServiceError(
                    _("Account verification failed: {0}").format(response.message)
                )
                
            # Parse the response
            content = response.data
            
            # Format the verification result
            result = {
                'customer_name': content.get('Customer_Name') or content.get('name'),
                'account_number': content.get('account_number') or account_number,
                'provider': provider,
                'verified': True,
            }
                
            return result
        except Exception as e:
            raise VTpassServiceError(
                _("Error verifying account: {0}").format(str(e))
            ) from e
    
    @transaction.atomic
    def purchase(
        self, account_number: str, provider: str, plan: str, phone: str,
        reference: Optional[str] = None, user=None, 
        email: Optional[str] = None, callback_url: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Pay for an internet subscription.
        
        Args:
            account_number (str): The account number
            provider (str): The internet provider code
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
            'account_number': account_number,
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
            verification_code=account_number,
            callback_url=callback_url,
            customer_data={
                'account_number': account_number,
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
                    'billersCode': account_number,
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
                _("Internet subscription payment failed: {0}").format(str(e))
            ) from e
    
    def verify_transaction(self, reference: str) -> Transaction:
        """
        Verify an internet subscription transaction.
        
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