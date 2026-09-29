"""
Airtime views for the VTpass API.
This module defines views for airtime operations.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import TransactionSerializer, TransactionCreateSerializer
from vtpass.services.airtime import AirtimeService
from vtpass.constants import NetworkProvider
from vtpass.exceptions import VTpassError


class AirtimePurchaseSerializer(TransactionCreateSerializer):
    """
    Serializer for purchasing airtime.
    """
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=50
    )
    provider = serializers.ChoiceField(choices=[p[0] for p in NetworkProvider.CHOICES])
    
    def validate_amount(self, value):
        """Validate the amount."""
        if value < 50:
            raise serializers.ValidationError("Amount must be at least 50.")
        return value


class AirtimeViewSet(BaseViewSet):
    """
    API endpoint for airtime operations.
    Provides `providers`, `purchase`, and `verify` actions.
    """
    
    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        Get a list of airtime providers.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with airtime providers
        """
        service = AirtimeService()
        providers = service.get_providers()
        
        return self.get_success_response(
            providers,
            message="Airtime providers retrieved successfully"
        )
    
    @action(detail=False, methods=['post'])
    def purchase(self, request):
        """
        Purchase airtime.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the purchase data
        serializer = AirtimePurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Purchase airtime
            service = AirtimeService()
            transaction = service.purchase(
                phone=serializer.validated_data['phone'],
                amount=float(serializer.validated_data['amount']),
                provider=serializer.validated_data['provider'],
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
                message="Airtime purchase initiated successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify an airtime transaction.
        
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
            service = AirtimeService()
            transaction = service.verify_transaction(reference)
            
            # Return the transaction
            transaction_serializer = TransactionSerializer(transaction)
            
            return self.get_success_response(
                transaction_serializer.data,
                message="Transaction verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))