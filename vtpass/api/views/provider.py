"""
Provider views for the VTpass API.
This module defines views for provider operations.
"""

from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.response import Response

from vtpass.models import Provider
from vtpass.api.views.base import BaseViewSet
from vtpass.api.serializers import ProviderSerializer, ServiceSerializer
from vtpass.exceptions import VTpassError


class ProviderViewSet(
    BaseViewSet,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin
):
    """
    API endpoint for providers.
    Provides `list`, `retrieve`, and `services` actions.
    """
    queryset = Provider.objects.filter(active=True)
    serializer_class = ProviderSerializer
    filterset_fields = ['service_type', 'code', 'active']
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'service_type', 'created_at']
    ordering = ['service_type', 'name']
    
    @action(detail=True, methods=['get'])
    def services(self, request, pk=None):
        """
        Get services for a provider.
        
        Args:
            request: The request object
            pk: The provider ID
            
        Returns:
            Response: The API response with provider services
        """
        provider = self.get_object()
        
        # Get active services
        services = provider.services.filter(active=True)
        serializer = ServiceSerializer(services, many=True)
        
        return self.get_success_response(
            serializer.data,
            message="Provider services retrieved successfully"
        )
    
    @action(detail=False, methods=['get'])
    def by_type(self, request):
        """
        Get providers filtered by service type.
        
        Args:
            request: The request object
            
        Returns:
            Response: The API response with providers for the service type
        """
        # Get service type from query params
        service_type = request.query_params.get('type')
        
        if not service_type:
            return self.get_error_response("Service type is required")
        
        # Filter by service type
        queryset = self.get_queryset().filter(service_type=service_type)
        serializer = self.get_serializer(queryset, many=True)
        
        return self.get_success_response(
            serializer.data,
            message=f"Providers for service type '{service_type}' retrieved successfully"
        )