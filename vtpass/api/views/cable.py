"""
Cable TV views for the VTpass API.
This module defines views for cable TV operations.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import TransactionSerializer, TransactionCreateSerializer
from vtpass.services.cable import CableTVService
from vtpass.constants import CableTVProvider
from vtpass.exceptions import VTpassError


class SmartcardVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying a smartcard.
    """
    smartcard_number = serializers.CharField(required=True, min_length=5, max_length=20)
    provider = serializers.ChoiceField(choices=[p[0] for p in CableTVProvider.CHOICES])


class CableTVPurchaseSerializer(TransactionCreateSerializer):
    """
    Serializer for purchasing cable TV subscription.
    """
    smartcard_number = serializers.CharField(required=True, min_length=5, max_length=20)
    provider = serializers.ChoiceField(choices=[p[0] for p in CableTVProvider.CHOICES])
    plan = serializers.CharField(required=True)
    
    def validate(self, data):
        """Validate the data."""
        # Additional validation can be added here
        return data


class CableTVViewSet(BaseViewSet):
    """
    API endpoint for cable TV operations.
    Provides `providers`, `plans`, `verify_smartcard`, `purchase`, and `verify` actions.
    """
    
    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        Get a list of cable TV providers.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with cable TV providers
        """
        service = CableTVService()
        providers = service.get_providers()
        
        return self.get_success_response(
            providers,
            message="Cable TV providers retrieved successfully"
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
            service = CableTVService()
            plans = service.get_plans(provider)
            
            return self.get_success_response(
                plans,
                message=f"Subscription plans for {provider} retrieved successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify_smartcard(self, request):
        """
        Verify a smartcard.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the smartcard verification data
        serializer = SmartcardVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Verify the smartcard
            service = CableTVService()
            result = service.verify_smartcard(
                smartcard_number=serializer.validated_data['smartcard_number'],
                provider=serializer.validated_data['provider']
            )
            
            return self.get_success_response(
                result,
                message="Smartcard verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def purchase(self, request):
        """
        Purchase a cable TV subscription.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the purchase data
        serializer = CableTVPurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Purchase subscription
            service = CableTVService()
            transaction = service.purchase(
                smartcard_number=serializer.validated_data['smartcard_number'],
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
                message="Cable TV subscription purchase initiated successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify a cable TV subscription transaction.
        
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
            service = CableTVService()
            transaction = service.verify_transaction(reference)
            
            # Return the transaction
            transaction_serializer = TransactionSerializer(transaction)
            
            return self.get_success_response(
                transaction_serializer.data,
                message="Transaction verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))