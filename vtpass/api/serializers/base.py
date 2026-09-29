"""
Base serializers for the VTpass API.
This module defines base serializers that other serializers inherit from.
"""

from rest_framework import serializers


class BaseModelSerializer(serializers.ModelSerializer):
    """
    Base serializer for all VTpass model serializers.
    This adds common functionality to all serializers.
    """
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the serializer.
        This adds support for dynamic fields.
        """
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop('fields', None)
        
        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)