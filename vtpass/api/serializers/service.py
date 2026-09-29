"""
Service serializers for the VTpass API.
This module defines serializers for Service and ServiceVariation models.
"""

from rest_framework import serializers

from vtpass.models import Service, ServiceVariation
from vtpass.api.serializers.base import BaseModelSerializer


class ServiceVariationSerializer(BaseModelSerializer):
    """
    Serializer for the ServiceVariation model.
    """
    class Meta:
        model = ServiceVariation
        fields = [
            'id', 'name', 'variation_code', 'description',
            'amount', 'active', 'meta_data', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class ServiceSerializer(BaseModelSerializer):
    """
    Serializer for the Service model.
    """
    service_type_display = serializers.SerializerMethodField()
    provider_name = serializers.SerializerMethodField()
    variations = ServiceVariationSerializer(many=True, read_only=True)
    
    class Meta:
        model = Service
        fields = [
            'id', 'name', 'service_id', 'service_type', 'service_type_display',
            'provider', 'provider_name', 'description', 'icon',
            'requires_verification', 'verification_field',
            'supports_recurring', 'min_amount', 'max_amount',
            'active', 'meta_data', 'variations', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_service_type_display(self, obj):
        """Get the display value for service_type."""
        return obj.get_service_type_display()
    
    def get_provider_name(self, obj):
        """Get the provider name."""
        return obj.provider.name if obj.provider else None