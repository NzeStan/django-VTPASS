"""
Data views for the VTpass API.
This module defines views for data operations.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import TransactionSerializer, TransactionCreateSerializer
from vtpass.services.data import DataService
from vtpass.constants import NetworkProvider
from vtpass.exceptions import VTpassError


class DataPurchaseSerializer(TransactionCreateSerializer):
    """
    Serializer for purchasing data plans.
    """
    provider = serializers.ChoiceField(choices=[p[0] for p in NetworkProvider.CHOICES])
    plan = serializers.CharField(required=True)
    
    def validate(self, data):
        """Validate the data."""
        # Additional validation can be added here
        return data


class DataViewSet(BaseViewSet):
    """
    API endpoint for data operations.
    Provides `providers`, `plans`, `purchase`, and `verify` actions.
    """
    
    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        Get a list of data providers.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with data providers
        """
        service = DataService()
        providers = service.get_providers()
        
        return self.get_success_response(
            providers,
            message="Data providers retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def plans(self, request):
        """
        Get data plans for a provider.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with data plans
        """
        # Get provider from query params
        provider = request.query_params.get('provider')
        
        if not provider:
            return self.get_error_response("Provider is required")
            
        try:
            # Get plans for the provider
            service = DataService()
            plans = service.get_data_plans(provider)
            
            return self.get_success_response(
                plans,
                message=f"Data plans for {provider} retrieved successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def purchase(self, request):
        """
        Purchase a data plan.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the purchase data
        serializer = DataPurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Purchase data plan
            service = DataService()
            transaction = service.purchase(
                phone=serializer.validated_data['phone'],
                provider=serializer.validated_data['provider'],
                plan=serializer.validated_data['plan'],
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
                message="Data plan purchase initiated successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify a data plan transaction.
        
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
            service = DataService()
            transaction = service.verify_transaction(reference)
            
            # Return the transaction
            transaction_serializer = TransactionSerializer(transaction)
            
            return self.get_success_response(
                transaction_serializer.data,
                message="Transaction verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))