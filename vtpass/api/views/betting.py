"""
Betting views for the VTpass API.
This module defines views for betting operations.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import TransactionSerializer, TransactionCreateSerializer
from vtpass.services.betting import BettingService
from vtpass.exceptions import VTpassError


class AccountVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying a betting account.
    """
    account_number = serializers.CharField(required=True, min_length=5, max_length=20)
    provider = serializers.CharField(required=True)


class BettingPurchaseSerializer(TransactionCreateSerializer):
    """
    Serializer for funding betting wallet.
    """
    account_number = serializers.CharField(required=True, min_length=5, max_length=20)
    provider = serializers.CharField(required=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=100)
    
    def validate_amount(self, value):
        """Validate the amount."""
        if value < 100:
            raise serializers.ValidationError("Amount must be at least 100.")
        return value


class BettingViewSet(BaseViewSet):
    """
    API endpoint for betting operations.
    Provides `providers`, `verify_account`, `purchase`, and `verify` actions.
    """
    
    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        Get a list of betting providers.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with betting providers
        """
        try:
            service = BettingService()
            providers = service.get_providers()
            
            return self.get_success_response(
                providers,
                message="Betting providers retrieved successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify_account(self, request):
        """
        Verify a betting account.
        
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
            service = BettingService()
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
        Fund a betting wallet.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the purchase data
        serializer = BettingPurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Fund the wallet
            service = BettingService()
            transaction = service.purchase(
                account_number=serializer.validated_data['account_number'],
                provider=serializer.validated_data['provider'],
                amount=float(serializer.validated_data['amount']),
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
                message="Betting wallet funding initiated successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify a betting wallet funding transaction.
        
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
            service = BettingService()
            transaction = service.verify_transaction(reference)
            
            # Return the transaction
            transaction_serializer = TransactionSerializer(transaction)
            
            return self.get_success_response(
                transaction_serializer.data,
                message="Transaction verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))