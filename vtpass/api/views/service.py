"""
Service views for the VTpass API.
This module defines views for service operations.
"""

from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from vtpass.models import Service, ServiceVariation
from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import ServiceSerializer, ServiceVariationSerializer
from vtpass.exceptions import VTpassError


class ServiceViewSet(
    BaseViewSet,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin
):
    """
    API endpoint for services.
    Provides `list`, `retrieve`, and `variations` actions.
    """
    queryset = Service.objects.filter(active=True)
    serializer_class = ServiceSerializer
    filterset_fields = ['service_type', 'service_id', 'provider', 'active']
    search_fields = ['name', 'service_id', 'description']
    ordering_fields = ['name', 'service_type', 'created_at']
    ordering = ['service_type', 'name']
    
    @action(detail=True, methods=['get'])
    def variations(self, request, pk=None):
        """
        Get variations for a service.
        
        Args:
            request: The request object
            pk: The service ID
            
        Returns:
            Response: The API response with service variations
        """
        service = self.get_object()
        
        # Get active variations
        variations = service.variations.filter(active=True)
        serializer = ServiceVariationSerializer(variations, many=True)
        
        return self.get_success_response(
            serializer.data,
            message="Service variations retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """
        Get services grouped by type.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with services grouped by type
        """
        # Get service type from query params
        service_type = request.query_params.get('type')
        
        if service_type:
            # Filter by specific service type
            queryset = self.get_queryset().filter(service_type=service_type)
            serializer = self.get_serializer(queryset, many=True)
            
            return self.get_success_response(
                serializer.data,
                message=f"Services of type '{service_type}' retrieved successfully"
            )
        else:
            # Group all services by type
            result = {}
            for service in self.get_queryset():
                service_type = service.service_type
                if service_type not in result:
                    result[service_type] = []
                
                # Serialize the service
                serializer = self.get_serializer(service)
                result[service_type].append(serializer.data)
            
            return self.get_success_response(
                result,
                message="Services grouped by type retrieved successfully"
            )
    
    @action(detail=False, methods=['get'])
    def by_provider(self, request):
        """
        Get services for a specific provider.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with services for the provider
        """
        # Get provider code from query params
        provider_code = request.query_params.get('code')
        
        if not provider_code:
            return self.get_error_response("Provider code is required")
        
        # Filter by provider code
        queryset = self.get_queryset().filter(provider__code=provider_code)
        serializer = self.get_serializer(queryset, many=True)
        
        return self.get_success_response(
            serializer.data,
            message=f"Services for provider '{provider_code}' retrieved successfully"
        )