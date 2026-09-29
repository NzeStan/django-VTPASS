"""
Transaction serializers for the VTpass API.
This module defines serializers for Transaction model.
"""

from rest_framework import serializers

from vtpass.models import Transaction, Service, ServiceVariation
from vtpass.api.serializers.base import BaseModelSerializer
from vtpass.api.serializers.service import ServiceSerializer, ServiceVariationSerializer


class TransactionSerializer(BaseModelSerializer):
    """
    Serializer for the Transaction model.
    """
    service = ServiceSerializer(read_only=True)
    service_variation = ServiceVariationSerializer(read_only=True)
    status_display = serializers.SerializerMethodField()
    service_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Transaction
        fields = [
            'id', 'reference', 'transaction_id', 'amount', 'status',
            'status_display', 'service_type', 'service_type_display',
            'service', 'service_variation', 'phone', 'email',
            'verification_code', 'customer_data', 'response_message',
            'callback_url', 'meta_data', 'completed_at', 'created_at',
            'updated_at'
        ]
        read_only_fields = fields
    
    def get_status_display(self, obj):
        """Get the display value for status."""
        return obj.get_status_display()
    
    def get_service_type_display(self, obj):
        """Get the display value for service_type."""
        return obj.get_service_type_display()


class TransactionCreateSerializer(serializers.Serializer):
    """
    Serializer for creating a transaction.
    This is a base serializer that specific service serializers can inherit from.
    """
    reference = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(min_length=10, max_length=15)
    email = serializers.EmailField(required=False, allow_blank=True)
    callback_url = serializers.URLField(required=False, allow_blank=True)
    meta_data = serializers.JSONField(required=False, default=dict)
    
    def validate(self, data):
        """
        Validate the data.
        This method should be extended by child serializers.
        """
        return data