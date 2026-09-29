"""
Wallet serializers for the VTpass API.
This module defines serializers for Wallet and WalletTransaction models.
"""

from rest_framework import serializers

from vtpass.models import Wallet, WalletTransaction
from vtpass.api.serializers.base import BaseModelSerializer


class WalletTransactionSerializer(BaseModelSerializer):
    """
    Serializer for the WalletTransaction model.
    """
    transaction_type_display = serializers.SerializerMethodField()
    
    class Meta:
        model = WalletTransaction
        fields = [
            'id', 'wallet', 'amount', 'transaction_type',
            'transaction_type_display', 'reference', 'description',
            'meta_data', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_transaction_type_display(self, obj):
        """Get the display value for transaction_type."""
        return obj.get_transaction_type_display()


class WalletSerializer(BaseModelSerializer):
    """
    Serializer for the Wallet model.
    """
    username = serializers.SerializerMethodField()
    recent_transactions = serializers.SerializerMethodField()
    
    class Meta:
        model = Wallet
        fields = [
            'id', 'user', 'username', 'balance', 'active',
            'last_deposit_at', 'last_withdrawal_at',
            'meta_data', 'recent_transactions', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_username(self, obj):
        """Get the username of the wallet owner."""
        return obj.user.username if obj.user else None
    
    def get_recent_transactions(self, obj):
        """Get the most recent transactions for this wallet."""
        transactions = obj.transactions.order_by('-created_at')[:5]
        return WalletTransactionSerializer(transactions, many=True).data


class WalletDepositSerializer(serializers.Serializer):
    """
    Serializer for depositing funds into a wallet.
    """
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0.01
    )
    description = serializers.CharField(required=False, allow_blank=True)
    meta_data = serializers.JSONField(required=False, default=dict)
    
    def validate_amount(self, value):
        """Validate the amount."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value


class WalletWithdrawSerializer(serializers.Serializer):
    """
    Serializer for withdrawing funds from a wallet.
    """
    amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0.01
    )
    description = serializers.CharField(required=False, allow_blank=True)
    meta_data = serializers.JSONField(required=False, default=dict)
    
    def validate_amount(self, value):
        """Validate the amount."""
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        
        # Check if the wallet has sufficient balance
        wallet = self.context.get('wallet')
        if wallet and wallet.balance < value:
            raise serializers.ValidationError("Insufficient balance.")
            
        return value