"""
Water service module for the VTpass package.
This module provides services for water bill payments.
"""

from typing import Dict, List, Optional, Union, Any
from django.utils.translation import gettext_lazy as _
from django.db import transaction

from vtpass.services.base import BaseService
from vtpass.client import VTpassClient, VTpassResponse
from vtpass.models.transaction import Transaction
from vtpass.models.service import Service
from vtpass.exceptions import VTpassValidationError, VTpassServiceError
from vtpass.constants import ServiceType, Endpoints


class WaterService(BaseService):
    """
    Service for water bill payments.
    Provides methods for paying water bills.
    """
    service_type = ServiceType.WATER
    
    # Validation rules specific to water bills
    validation_rules = {
        'amount': {
            'required': True,
            'min_value': 500,  # Minimum water bill payment
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
        'account_number': {
            'required': True,
            'min_length': 5,
            'max_length': 30,
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
        Get a list of available water providers.
        
        Returns:
            list: A list of provider dictionaries with 'id' and 'name' keys
        """
        try:
            # Get the water providers from the API
            response = self.client.get_service_categories()
            
            if not response.success:
                raise VTpassServiceError(
                    _("Failed to fetch water providers: {0}").format(response.message)
                )
                
            # Parse the response
            content = response.data
            services = content.get('services') or []
            
            # Filter and format the water providers
            providers = []
            for service in services:
                service_type = service.get('serviceType', '').lower()
                if service_type == 'water':
                    provider = {
                        'id': service.get('serviceID'),
                        'name': service.get('name'),
                    }
                    providers.append(provider)
                
            return providers
        except Exception as e:
            raise VTpassServiceError(
                _("Error fetching water providers: {0}").format(str(e))
            ) from e
    
    def validate_purchase_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate data for water bill payment.
        
        Args:
            data (dict): The purchase data
            
        Returns:
            dict: The validated data
            
        Raises:
            VTpassValidationError: If validation fails
        """
        # Validate using base rules
        validated_data = self.validate_data(data)
        
        # Additional validation specific to water bills
        provider = validated_data.get('provider')
        if not provider:
            raise VTpassValidationError(
                _("Invalid provider."),
                errors={'provider': [_("Provider is required.")]}
            )
        
        return validated_data
    
    def verify_account(
        self, account_number: str, provider: str
    ) -> Dict[str, Any]:
        """
        Verify a water account.
        
        Args:
            account_number (str): The account number to verify
            provider (str): The water provider service ID
            
        Returns:
            dict: The verified account information
            
        Raises:
            VTpassServiceError: If the verification fails
        """
        try:
            # Verify the account through the API
            response = self.client.post(
                Endpoints.VERIFY_CUSTOMER, 
                data={
                    'billersCode': account_number, 
                    'serviceID': provider
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
                'address': content.get('Address') or content.get('address'),
                'account_number': content.get('Customer_ID') or account_number,
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
        self, account_number: str, provider: str, amount: float, phone: str,
        reference: Optional[str] = None, user=None, 
        email: Optional[str] = None, callback_url: Optional[str] = None,
        meta_data: Optional[Dict[str, Any]] = None
    ) -> Transaction:
        """
        Pay a water bill.
        
        Args:
            account_number (str): The water account number
            provider (str): The water provider service ID
            amount (float): The amount to pay
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
            'amount': amount,
            'phone': phone,
            'reference': reference,
        })
        
        # Get or create the service
        service = self.get_service_by_id(provider)
        if not service:
            # Try to fetch service info from API
            try:
                self.client.get_service_categories()
                service = self.get_service_by_id(provider)
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
            verification_code=account_number,
            callback_url=callback_url,
            customer_data={
                'account_number': account_number,
            },
            meta_data=meta_data or {},
        )
        
        try:
            # Make the API request to pay the water bill
            response = self.client.purchase(
                service_id=provider,
                amount=amount,
                phone=phone,
                reference=reference,
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
                _("Water bill payment failed: {0}").format(str(e))
            ) from e
    
    def verify_transaction(self, reference: str) -> Transaction:
        """
        Verify a water bill payment transaction.
        
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