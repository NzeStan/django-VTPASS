"""
Electricity views for the VTpass API.
This module defines views for electricity operations.
"""

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import serializers

from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import TransactionSerializer, TransactionCreateSerializer
from vtpass.services.electricity import ElectricityService
from vtpass.constants import ElectricityProvider, MeterType
from vtpass.exceptions import VTpassError


class MeterVerificationSerializer(serializers.Serializer):
    """
    Serializer for verifying a meter.
    """
    meter_number = serializers.CharField(required=True, min_length=5, max_length=30)
    provider = serializers.ChoiceField(choices=[p[0] for p in ElectricityProvider.CHOICES])
    meter_type = serializers.ChoiceField(choices=[m[0] for m in MeterType.CHOICES])


class ElectricityPurchaseSerializer(TransactionCreateSerializer):
    """
    Serializer for purchasing electricity.
    """
    meter_number = serializers.CharField(required=True, min_length=5, max_length=30)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=500)
    provider = serializers.ChoiceField(choices=[p[0] for p in ElectricityProvider.CHOICES])
    meter_type = serializers.ChoiceField(choices=[m[0] for m in MeterType.CHOICES])
    
    def validate_amount(self, value):
        """Validate the amount."""
        if value < 500:
            raise serializers.ValidationError("Amount must be at least 500.")
        return value


class ElectricityViewSet(BaseViewSet):
    """
    API endpoint for electricity operations.
    Provides `providers`, `meter_types`, `verify_meter`, `purchase`, and `verify` actions.
    """
    
    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        Get a list of electricity providers.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with electricity providers
        """
        service = ElectricityService()
        providers = service.get_providers()
        
        return self.get_success_response(
            providers,
            message="Electricity providers retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def meter_types(self, request):
        """
        Get a list of meter types.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with meter types
        """
        service = ElectricityService()
        meter_types = service.get_meter_types()
        
        return self.get_success_response(
            meter_types,
            message="Meter types retrieved successfully"
        )
    
    @action(detail=False, methods=['post'])
    def verify_meter(self, request):
        """
        Verify a meter.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the meter verification data
        serializer = MeterVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Verify the meter
            service = ElectricityService()
            result = service.verify_meter(
                meter_number=serializer.validated_data['meter_number'],
                provider=serializer.validated_data['provider'],
                meter_type=serializer.validated_data['meter_type']
            )
            
            return self.get_success_response(
                result,
                message="Meter verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def purchase(self, request):
        """
        Purchase electricity.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response
        """
        # Validate the purchase data
        serializer = ElectricityPurchaseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # Purchase electricity
            service = ElectricityService()
            transaction = service.purchase(
                meter_number=serializer.validated_data['meter_number'],
                amount=float(serializer.validated_data['amount']),
                provider=serializer.validated_data['provider'],
                meter_type=serializer.validated_data['meter_type'],
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
                message="Electricity purchase initiated successfully",
                status_code=status.HTTP_201_CREATED
            )
        except VTpassError as e:
            return self.get_error_response(str(e))
    
    @action(detail=False, methods=['post'])
    def verify(self, request):
        """
        Verify an electricity transaction.
        
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
            service = ElectricityService()
            transaction = service.verify_transaction(reference)
            
            # Return the transaction
            transaction_serializer = TransactionSerializer(transaction)
            
            return self.get_success_response(
                transaction_serializer.data,
                message="Transaction verified successfully"
            )
        except VTpassError as e:
            return self.get_error_response(str(e))