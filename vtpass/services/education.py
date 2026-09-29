"""
Education service module for the VTpass package.
This module provides services for education payments like WAEC, JAMB, etc.
"""

from typing import Dict, List, Optional, Union, Any
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from vtpass.services.base import BaseService
from vtpass.client import VTpassClient, VTpassResponse
from vtpass.models.transaction import Transaction
from vtpass.models.service import Service, ServiceVariation
from vtpass.exceptions import VTpassValidationError, VTpassServiceError
from vtpass.constants import ServiceType, Endpoints, EducationProvider


class EducationService(BaseService):
    """
    Service for education payments.
    Provides methods for making education payments like WAEC, JAMB, etc.
    """
    service_type = ServiceType.EDUCATION
    
    # Validation rules specific to education payments
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
        'quantity': {
            'required': False,
            'min_value': 1,
            'type': int,
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
        Get a list of available education providers.
        
        Returns:
            list: A list of provider dictionaries with 'id' and 'name' keys
        """
        return [
            {'id': provider[0], 'name': provider[1]} 
            for provider in EducationProvider.CHOICES
        ]
    
    def get_service_id_for_provider(self, provider: str) -> str:
        """
        Get the service ID for an education provider.
        
        Args:
            provider (str): The provider code (e.g., 'waec', 'jamb')
            
        Returns:
            str: The service ID for the provider
            
        Raises:
            VTpassServiceError: If the provider is not supported
        """
        if provider not in EducationProvider.CODES:
            raise VTpassServiceError(
                _("Unsupported education provider: {0}").format(provider)
            )
            
        return EducationProvider.CODES[provider]
    
    def get_products(self, provider: str) -> List[Dict[str, Any]]:
        """
        Get a list of products for a provider.
        
        Args:
            provider (str): The provider code
            
        Returns:
            list: A list of product dictionaries
            
        Raises:
            VTpassServiceError: If the provider is not supported or if fetching products fails
        """
        service_id = self.get_service_id_for_provider(provider)
        
        try:
            # Get the products from the API
            response = self.client.get_service_variations(service_id)
            
            if not response.success:
                raise VTpassServiceError(
                    _("Failed to fetch products: {0}").format(response.message)
                )
                
            # Parse the response
            content = response.data
            variations = content.get('varations') or content.get('variations') or []
            
            # Format the products
            products = []
            for variation in variations:
                product = {
                    'code': variation.get('variation_code'),
                    'name': variation.get('name'),
                    'amount': variation.get('variation_amount'),
                    'description': variation.get('variation_desc') or '',
                }
                products.append(product)
                
            return products
        except Exception as e:
            raise VTpassServiceError(
                _("Error fetching products: {0}").format(str(e))
            ) from e
    
    def validate_purchase_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data for education payment.
        
        Args:
            data (dict): The purchase data
            
        Returns:
            dict: The validated data
            
        Raises:
            VTpassValidationError: If validation fails
        """
        # Validate using base rules
        validated_data = self.validate_data(data)
        
        # Additional validation specific to education payments
        provider = validated_data.get('provider')
        if provider and provider not in [p[0] for p in EducationProvider.CHOICES]:
            raise VTpassValidationError(
                _("Invalid provider."),
                errors={'provider': [_("Provider not supported.")]}
            )
        
        return validated_data
    
    @transaction.atomic
    def purchase(
        self, provider: str, product: str, phone: str, quantity: int = 1,
        reference: Optional[str] = None, user=None, 
        email: Optional[str] = None, callback_url: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Make an education payment.
        
        Args:
            provider (str): The education provider code
            product (str): The product variation code
            phone (str): The phone number
            quantity (int, optional): The quantity to purchase. Defaults to 1.
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
            'provider': provider,
            'product': product,
            'phone': phone,
            'quantity': quantity,
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
        variation = self.get_variation_by_code(service, product)
        if not variation:
            # Try to fetch variations from API
            try:
                # Fetch variations from API to update cache
                self.get_products(provider)
                variation = self.get_variation_by_code(service, product)
                if not variation:
                    raise VTpassServiceError(
                        _("Product not found: {0}").format(product)
                    )
            except Exception as e:
                raise VTpassServiceError(
                    _("Error fetching product information: {0}").format(str(e))
                ) from e
        
        # Calculate the total amount
        amount = variation.amount * quantity
        
        # Generate a reference if not provided
        if not reference:
            reference = self.generate_reference()
            
        # Create the transaction record
        transaction = self.create_transaction(
            service=service,
            amount=amount,
            phone=phone,
            reference=reference,
            variation=variation,
            user=user,
            email=email,
            callback_url=callback_url,
            customer_data={
                'quantity': quantity,
            },
            meta_data=meta_data or {},
        )
        
        try:
            # Make the API request to make the education payment
            response = self.client.purchase(
                service_id=service_id,
                amount=amount,
                phone=phone,
                reference=reference,
                variation_code=product,
                customer_data={
                    'quantity': quantity,
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
                _("Education payment failed: {0}").format(str(e))
            ) from e
    
    def verify_transaction(self, reference: str) -> Transaction:
        """
        Verify an education payment transaction.
        
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