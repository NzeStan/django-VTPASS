from decimal import Decimal

from rest_framework import serializers

from vtpass.models import Service, ServiceCategory, Variation


class ServiceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceCategory
        fields = ("identifier", "name")


class ServiceSerializer(serializers.ModelSerializer):
    category = serializers.CharField(source="category.identifier")

    class Meta:
        model = Service
        fields = ("service_id", "name", "category", "image", "minimum_amount", "maximum_amount", "convenience_fee")


class VariationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Variation
        fields = ("variation_code", "name", "amount", "fixed_price")


class VerifySerializer(serializers.Serializer):
    service_id = serializers.CharField(max_length=64)
    billers_code = serializers.CharField(max_length=128)
    type = serializers.CharField(max_length=64, required=False, allow_blank=True)


class QuoteRequestSerializer(serializers.Serializer):
    service_id = serializers.CharField(max_length=64)
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False, min_value=Decimal("1"))
    variation_code = serializers.CharField(max_length=128, required=False, allow_blank=True)
    quantity = serializers.IntegerField(required=False, min_value=1, max_value=100, default=1)
    operator_id = serializers.CharField(required=False)
    product_type_id = serializers.CharField(required=False)
