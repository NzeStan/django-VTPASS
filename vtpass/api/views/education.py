"""
Education views for the VTpass API.
This module defines views for education operations.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import TransactionSerializer, TransactionCreateSerializer
from vtpass.services.education import EducationService
from vtpass.constants import EducationProvider
from vtpass.exceptions import VTpassError


class EducationPurchaseSerializer(TransactionCreateSerializer):
    """
    Serializer for purchasing education products.
    """
    provider = serializers.ChoiceField(choices=[p[0] for p in EducationProvider.CHOICES])
    product = serializers.CharField(required=True)
    quantity = serializers.IntegerField(required=False, min_value=1, default=1)
    
    def validate(self, data):
        """Validate the data."""
        # Additional validation can be added here
        return data


class EducationViewSet(BaseViewSet):
    """
    API endpoint for education operations.
    Provides `providers`, `products`, `purchase`, and `verify` actions.
    """
    
    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        Get a list of education providers.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with education providers
        """
        service = EducationService()
        providers = service.get_providers()
        
        return self.get_success_response(
            providers,
            message="Education providers retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def products(self, request):
        """
        Get products for a provider.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with education products
        """
        # Get provider from query params
        provider = request.query_params.get('provider')
        
        if not provider:
            return self.get_error_response("Provider is required")
            
        try:
            # Get products for the provider
            service = EducationService()
            products = service.get_products(provider)
            
            return self.get_success_response(
                products,
                message=f"Products for {provider} retrieved successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def purchase(self, request):
        """
        Purchase an education product.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the purchase data
        serializer = EducationPurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Purchase the product
            service = EducationService()
            transaction = service.purchase(
                provider=serializer.validated_data['provider'],
                product=serializer.validated_data['product'],
                phone=serializer.validated_data['phone'],
                quantity=serializer.validated_data.get('quantity', 1),
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
                message="Education product purchase initiated successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify an education product transaction.
        
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
            service = EducationService()
            transaction = service.verify_transaction(reference)
            
            # Return the transaction
            transaction_serializer = TransactionSerializer(transaction)
            
            return self.get_success_response(
                transaction_serializer.data,
                message="Transaction verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))