"""
Admin interface for the VTpass package.
This module defines admin models for the VTpass package.
"""

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from vtpass.models import (
    Transaction, Service, ServiceVariation, Provider,
    Commission, CommissionRate, Wallet, WalletTransaction
)


class ServiceVariationInline(admin.TabularInline):
    """Inline admin for service variations."""
    model = ServiceVariation
    extra = 0
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'name', 'variation_code', 'amount', 'description', 'active',
        'created_at', 'updated_at'
    ]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """Admin interface for services."""
    list_display = [
        'name', 'service_id', 'service_type', 'provider',
        'active', 'variations_count', 'min_amount', 'max_amount',
        'created_at'
    ]
    list_filter = ['service_type', 'active', 'requires_verification', 'supports_recurring']
    search_fields = ['name', 'service_id', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'name', 'service_id', 'service_type', 'provider', 'description',
        'icon', 'requires_verification', 'verification_field',
        'supports_recurring', 'min_amount', 'max_amount', 'active',
        'meta_data', 'created_at', 'updated_at'
    ]
    inlines = [ServiceVariationInline]
    
    def variations_count(self, obj):
        """Get the number of variations for this service."""
        return obj.variations.count()
    variations_count.short_description = _('Variations')


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    """Admin interface for providers."""
    list_display = [
        'name', 'code', 'service_type', 'active', 'services_count',
        'created_at'
    ]
    list_filter = ['service_type', 'active']
    search_fields = ['name', 'code', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'name', 'code', 'service_type', 'logo', 'description',
        'active', 'meta_data', 'created_at', 'updated_at'
    ]
    
    def services_count(self, obj):
        """Get the number of services for this provider."""
        return obj.services.count()
    services_count.short_description = _('Services')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """Admin interface for transactions."""
    list_display = [
        'reference', 'service_type', 'service_name', 'transaction_id',
        'amount', 'status', 'created_at', 'completed_at', 'user_link'
    ]
    list_filter = ['status', 'service_type', 'created_at', 'completed_at']
    search_fields = [
        'reference', 'transaction_id', 'phone', 'email',
        'user__username', 'user__email'
    ]
    readonly_fields = [
        'reference', 'transaction_id', 'status', 'service', 'service_type',
        'service_variation', 'completed_at', 'created_at', 'updated_at',
        'response_data', 'response_message'
    ]
    fields = [
        'reference', 'transaction_id', 'status', 'amount',
        'service', 'service_type', 'service_variation',
        'phone', 'email', 'user', 'verification_code',
        'customer_data', 'callback_url', 'meta_data',
        'response_data', 'response_message',
        'completed_at', 'created_at', 'updated_at'
    ]
    actions = ['verify_transactions']
    
    def service_name(self, obj):
        """Get the service name."""
        return obj.service.name
    service_name.short_description = _('Service')
    
    def user_link(self, obj):
        """Get a link to the user admin."""
        if obj.user:
            url = reverse(
                'admin:auth_user_change',
                args=[obj.user.pk]
            )
            return format_html('<a href="{}">{}</a>', url, obj.user)
        return '-'
    user_link.short_description = _('User')
    
    def verify_transactions(self, request, queryset):
        """Admin action to verify selected transactions."""
        from vtpass.services.base import BaseService
        service = BaseService()
        
        updated = 0
        for transaction in queryset:
            if transaction.is_pending:
                service.check_transaction_status(transaction)
                updated += 1
                
        self.message_user(
            request,
            _("{} transactions have been verified.").format(updated)
        )
    verify_transactions.short_description = _("Verify selected transactions")


@admin.register(CommissionRate)
class CommissionRateAdmin(admin.ModelAdmin):
    """Admin interface for commission rates."""
    list_display = [
        'service_type', 'rate_percentage', 'active',
        'created_at', 'updated_at'
    ]
    list_filter = ['service_type', 'active']
    search_fields = ['service_type', 'description']
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'service_type', 'rate', 'description',
        'active', 'created_at', 'updated_at'
    ]


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    """Admin interface for commissions."""
    list_display = [
        'transaction_reference', 'amount', 'rate_percentage',
        'is_paid', 'paid_at', 'user_link', 'created_at'
    ]
    list_filter = ['is_paid', 'paid_at', 'created_at']
    search_fields = [
        'transaction__reference', 'user__username', 'user__email',
        'description'
    ]
    readonly_fields = ['transaction', 'amount', 'rate', 'created_at', 'updated_at']
    fields = [
        'transaction', 'amount', 'rate', 'user',
        'is_paid', 'paid_at', 'description', 'meta_data',
        'created_at', 'updated_at'
    ]
    actions = ['mark_as_paid']
    
    def transaction_reference(self, obj):
        """Get the transaction reference."""
        return obj.transaction.reference
    transaction_reference.short_description = _('Transaction')
    
    def rate_percentage(self, obj):
        """Get the rate as a percentage."""
        return f"{obj.rate * 100:.2f}%"
    rate_percentage.short_description = _('Rate')
    
    def user_link(self, obj):
        """Get a link to the user admin."""
        if obj.user:
            url = reverse(
                'admin:auth_user_change',
                args=[obj.user.pk]
            )
            return format_html('<a href="{}">{}</a>', url, obj.user)
        return '-'
    user_link.short_description = _('User')
    
    def mark_as_paid(self, request, queryset):
        """Admin action to mark selected commissions as paid."""
        from django.utils import timezone
        
        updated = queryset.filter(is_paid=False).update(
            is_paid=True,
            paid_at=timezone.now()
        )
                
        self.message_user(
            request,
            _("{} commissions have been marked as paid.").format(updated)
        )
    mark_as_paid.short_description = _("Mark selected commissions as paid")


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    """Admin interface for wallets."""
    list_display = [
        'user_link', 'balance', 'active',
        'last_deposit_at', 'last_withdrawal_at', 'created_at'
    ]
    list_filter = ['active', 'created_at', 'last_deposit_at', 'last_withdrawal_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = [
        'balance', 'last_deposit_at', 'last_withdrawal_at',
        'created_at', 'updated_at'
    ]
    fields = [
        'user', 'balance', 'active', 'meta_data',
        'last_deposit_at', 'last_withdrawal_at',
        'created_at', 'updated_at'
    ]
    
    def user_link(self, obj):
        """Get a link to the user admin."""
        url = reverse(
            'admin:auth_user_change',
            args=[obj.user.pk]
        )
        return format_html('<a href="{}">{}</a>', url, obj.user)
    user_link.short_description = _('User')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    """Admin interface for wallet transactions."""
    list_display = [
        'transaction_type', 'amount', 'wallet_user',
        'reference', 'created_at'
    ]
    list_filter = ['transaction_type', 'created_at']
    search_fields = [
        'wallet__user__username', 'wallet__user__email',
        'reference', 'description'
    ]
    readonly_fields = ['created_at', 'updated_at']
    fields = [
        'wallet', 'transaction_type', 'amount',
        'reference', 'description', 'meta_data',
        'created_at', 'updated_at'
    ]
    
    def wallet_user(self, obj):
        """Get the wallet user."""
        return obj.wallet.user
    wallet_user.short_description = _('User')