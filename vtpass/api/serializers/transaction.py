from rest_framework import serializers

from vtpass.constants import ResponseCode, Status
from vtpass.models import Transaction


def public_message(txn):
    """A customer-safe message: merchant-side problems (low VTpass balance, IP whitelisting...) are never exposed."""
    if txn.status == Status.SUCCESSFUL:
        return "Transaction successful."
    if txn.status in Status.open():
        return "Transaction is processing. You will be notified once it completes."
    refund = " Your payment has been refunded." if txn.refunded else ""
    if txn.status == Status.REVERSED:
        return "Transaction was reversed." + refund
    if txn.response_code in ResponseCode.MERCHANT_ERROR_CODES or not txn.response_code:
        return "This service is temporarily unavailable." + refund
    return (txn.response_description or "Transaction failed.").capitalize() + refund


class TransactionSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="uid", read_only=True)
    reference = serializers.CharField(source="request_id", read_only=True)
    message = serializers.SerializerMethodField()
    token = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = (
            "id", "reference", "status", "message", "category", "service_id", "product_name",
            "variation_code", "billers_code", "phone", "quantity", "amount", "fee", "discount",
            "amount_charged", "cashback", "cashback_paid", "currency", "refunded", "refund_amount",
            "token", "purchased_code", "vend_details", "created_at", "completed_at",
        )
        read_only_fields = fields

    def get_message(self, obj):
        return public_message(obj)

    def get_token(self, obj):
        return obj.token
