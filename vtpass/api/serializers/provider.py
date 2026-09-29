"""
Provider serializers for the VTpass API.
This module defines serializers for Provider model.
"""

from rest_framework import serializers

from vtpass.models import Provider
from vtpass.api.serializers.base import BaseModelSerializer


class ProviderSerializer(BaseModelSerializer):
    """
    Serializer for the Provider model.
    """
    service_type_display = serializers.SerializerMethodField()
    services_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Provider
        fields = [
            'id', 'name', 'code', 'service_type', 'service_type_display',
            'logo', 'description', 'active', 'meta_data',
            'services_count', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_service_type_display(self, obj):
        """Get the display value for service_type."""
        return obj.get_service_type_display()
    
    def get_services_count(self, obj):
        """Get the number of services for this provider."""
        return obj.services.count()