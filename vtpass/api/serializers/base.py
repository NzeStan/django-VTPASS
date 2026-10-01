from decimal import Decimal

from rest_framework import serializers

from vtpass.utils import is_valid_nigerian_phone, normalize_phone


class PhoneField(serializers.CharField):
    """Nigerian phone number, normalised to the 080... format."""

    def __init__(self, nigerian=True, **kwargs):
        self.nigerian = nigerian
        kwargs.setdefault("max_length", 20)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = normalize_phone(super().to_internal_value(data))
        if self.nigerian and not is_valid_nigerian_phone(value):
            raise serializers.ValidationError("Enter a valid Nigerian phone number.")
        if not self.nigerian and len(value) < 7:
            raise serializers.ValidationError("Enter a valid phone number.")
        return value


class MoneyField(serializers.DecimalField):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("min_value", Decimal("1"))
        super().__init__(**kwargs)


class PurchaseOptionsSerializer(serializers.Serializer):
    """Fields accepted by every purchase endpoint."""

    email = serializers.EmailField(required=False, allow_blank=True)
    save_beneficiary = serializers.BooleanField(required=False, default=False)
    metadata = serializers.DictField(required=False, default=dict)

    def validate_metadata(self, value):
        if len(str(value)) > 2000:
            raise serializers.ValidationError("Metadata is too large.")
        return value
