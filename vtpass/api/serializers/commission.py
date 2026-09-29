"""
Commission serializers for the VTpass API.
This module defines serializers for Commission and CommissionRate models.
"""

from rest_framework import serializers

from vtpass.models import Commission, CommissionRate
from vtpass.api.serializers.base import BaseModelSerializer
from vtpass.api.serializers.transaction import TransactionSerializer


class CommissionRateSerializer(BaseModelSerializer):
    """
    Serializer for the CommissionRate model.
    """
    service_type_display = serializers.SerializerMethodField()
    rate_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = CommissionRate
        fields = [
            'id', 'service_type', 'service_type_display', 'rate',
            'rate_percentage', 'description', 'active',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_service_type_display(self, obj):
        """Get the display value for service_type."""
        return obj.get_service_type_display()
    
    def get_rate_percentage(self, obj):
        """Get the rate as a percentage."""
        return f"{obj.rate * 100:.2f}%"


class CommissionSerializer(BaseModelSerializer):
    """
    Serializer for the Commission model.
    """
    transaction = TransactionSerializer(read_only=True)
    rate_percentage = serializers.SerializerMethodField()
    username = serializers.SerializerMethodField()
    
    class Meta:
        model = Commission
        fields = [
            'id', 'transaction', 'amount', 'rate', 'rate_percentage',
            'user', 'username', 'is_paid', 'paid_at', 'description',
            'meta_data', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_rate_percentage(self, obj):
        """Get the rate as a percentage."""
        return f"{obj.rate * 100:.2f}%"
    
    def get_username(self, obj):
        """Get the username of the commission owner."""
        return obj.user.username if obj.user else None