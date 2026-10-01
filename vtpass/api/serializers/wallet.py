from rest_framework import serializers

from vtpass.models import Beneficiary, WalletEntry


class WalletEntrySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uid", read_only=True)
    transaction_reference = serializers.CharField(source="transaction.request_id", default=None, read_only=True)

    class Meta:
        model = WalletEntry
        fields = (
            "id", "direction", "kind", "amount", "balance_before", "balance_after", "reference",
            "description", "transaction_reference", "created_at",
        )
        read_only_fields = fields


class BeneficiarySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uid", read_only=True)

    class Meta:
        model = Beneficiary
        fields = (
            "id", "category", "service_id", "billers_code", "nickname", "customer_name", "extra",
            "use_count", "last_used_at", "created_at",
        )
        read_only_fields = ("id", "use_count", "last_used_at", "created_at")
