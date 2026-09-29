"""
Internet views for the VTpass API.
This module defines views for internet operations.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import TransactionSerializer, TransactionCreateSerializer
from vtpass.services.internet import InternetService
from vtpass.constants import InternetProvider
from vtpass.exceptions import VTpassError


class AccountVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying an internet account.
    """
    account_number = serializers.CharField(required=True, min_length=5, max_length=20)
    provider = serializers.ChoiceField(choices=[p[0] for p in InternetProvider.CHOICES])


class InternetPurchaseSerializer(TransactionCreateSerializer):
    """
    Serializer for purchasing internet subscription.
    """
    account_number = serializers.CharField(required=True, min_length=5, max_length=20)
    provider = serializers.ChoiceField(choices=[p[0] for p in InternetProvider.CHOICES])
    plan = serializers.CharField(required=True)
    
    def validate(self, data):
        """Validate the data."""
        # Additional validation can be added here
        return data


class InternetViewSet(BaseViewSet):
    """
    API endpoint for internet operations.
    Provides `providers`, `plans`, `verify_account`, `purchase`, and `verify` actions.
    """
    
    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        Get a list of internet providers.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with internet providers
        """
        service = InternetService()
        providers = service.get_providers()
        
        return self.get_success_response(
            providers,
            message="Internet providers retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def plans(self, request):
        """
        Get subscription plans for a provider.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with subscription plans
        """
        # Get provider from query params
        provider = request.query_params.get('provider')
        
        if not provider:
            return self.get_error_response("Provider is required")
            
        try:
            # Get plans for the provider
            service = InternetService()
            plans = service.get_plans(provider)
            
            return self.get_success_response(
                plans,
                message=f"Subscription plans for {provider} retrieved successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify_account(self, request):
        """
        Verify an internet account.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the account verification data
        serializer = AccountVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Verify the account
            service = InternetService()
            result = service.verify_account(
                account_number=serializer.validated_data['account_number'],
                provider=serializer.validated_data['provider']
            )
            
            return self.get_success_response(
                result,
                message="Account verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def purchase(self, request):
        """
        Purchase an internet subscription.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the purchase data
        serializer = InternetPurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Purchase subscription
            service = InternetService()
            transaction = service.purchase(
                account_number=serializer.validated_data['account_number'],
                provider=serializer.validated_data['provider'],
                plan=serializer.validated_data['plan'],
                phone=serializer.validated_data['phone'],
                reference=serializer.validated_data.get('reference'),
                user=request.user,
                email=serializer.validated_data.get('email'),
                callback_url=serializer.validated_data.get('callback_url'),
                meta_data=serializer.validated_data.get('meta_data', {})
            )
            
            # Return the transaction
            transaction_serializer = TransactionSerializer(transaction)
            
            return self.get_success_response(
                transaction_serializer.data,
                message="Internet subscription purchase initiated successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify an internet subscription transaction.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Get the reference from the request data
        reference = request.data.get('reference')
        
        if not reference:
            return self.get_error_response("Transaction reference is required")
        
        try:
            # Verify the transaction
            service = InternetService()
            transaction = service.verify_transaction(reference)
            
            # Return the transaction
            transaction_serializer = TransactionSerializer(transaction)
            
            return self.get_success_response(
                transaction_serializer.data,
                message="Transaction verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))