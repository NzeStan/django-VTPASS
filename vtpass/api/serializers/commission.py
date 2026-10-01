from rest_framework import serializers


class QuoteSerializer(serializers.Serializer):
    face_value = serializers.DecimalField(max_digits=14, decimal_places=2)
    fee = serializers.DecimalField(max_digits=14, decimal_places=2)
    discount = serializers.DecimalField(max_digits=14, decimal_places=2)
    cashback = serializers.DecimalField(max_digits=14, decimal_places=2)
    amount_payable = serializers.DecimalField(max_digits=14, decimal_places=2)
    currency = serializers.CharField()
