"""
Django admin. Ledgers (transactions, wallet entries, webhook events, SMS) are
read-only on purpose: money must only move through the services layer so every
change is locked, audited and signalled.
"""

from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from vtpass.models import (
    Beneficiary,
    PricingRule,
    Service,
    ServiceCategory,
    SMSMessage,
    Transaction,
    Variation,
    Wallet,
    WalletEntry,
    WebhookEvent,
)


class ReadOnlyAdminMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _vtpass():
    from vtpass.services import VTpass

    return VTpass()


@admin.register(Transaction)
class TransactionAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "request_id", "user", "service_id", "billers_code", "amount", "amount_charged", "status",
        "response_code", "created_at",
    )
    list_filter = ("status", "category", "service_id", "refunded", "cashback_paid", "created_at")
    search_fields = ("request_id", "vtpass_transaction_id", "billers_code", "phone", "email", "user__username")
    date_hierarchy = "created_at"
    list_select_related = ("user",)
    actions = ("requery_selected",)
    fieldsets = (
        (None, {"fields": ("uid", "request_id", "vtpass_transaction_id", "user", "status", "channel", "client_ip")}),
        (_("Product"), {"fields": (
            "category", "service_id", "product_name", "variation_code", "billers_code", "phone", "email", "quantity",
        )}),
        (_("Money"), {"fields": (
            "currency", "amount", "fee", "discount", "amount_charged", "cashback", "cashback_paid", "cost",
            "vtpass_commission", "vtpass_commission_details", "pricing", "wallet_charged", "refunded",
            "refund_amount",
        )}),
        (_("Outcome"), {"fields": (
            "response_code", "response_description", "error_message", "purchased_code", "vend_details",
        )}),
        (_("Raw"), {"classes": ("collapse",), "fields": ("payload", "response", "metadata")}),
        (_("Timing"), {"fields": (
            "created_at", "updated_at", "completed_at", "requery_count", "last_requeried_at", "next_requery_at",
        )}),
    )

    @admin.action(description=_("Requery selected open transactions"), permissions=["requery"])
    def requery_selected(self, request, queryset):
        vt = _vtpass()
        done = 0
        for txn in queryset.filter(status__in=("initiated", "pending")):
            vt.requery(txn)
            done += 1
        self.message_user(request, _("%d transaction(s) requeried.") % done, messages.SUCCESS)

    def has_requery_permission(self, request):
        return request.user.has_perm("vtpass.requery_transaction")


@admin.register(PricingRule)
class PricingRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name", "is_active", "priority", "category", "service_id", "variation_code", "user_group",
        "fee_display", "discount_display", "cashback_display", "starts_at", "ends_at",
    )
    list_filter = ("is_active", "category", "user_group")
    search_fields = ("name", "service_id", "variation_code")
    list_editable = ("is_active", "priority")
    fieldsets = (
        (None, {"fields": ("name", "is_active", "priority", "description")}),
        (_("Applies to"), {"fields": (
            "category", "service_id", "variation_code", "user_group", "min_amount", "max_amount",
            "starts_at", "ends_at",
        )}),
        (_("Convenience fee"), {"fields": ("fee_type", "fee_value", "fee_min", "fee_cap")}),
        (_("Instant discount"), {"fields": ("discount_type", "discount_value", "discount_cap")}),
        (_("Cashback"), {"fields": ("cashback_type", "cashback_value", "cashback_cap")}),
    )

    @staticmethod
    def _fmt(kind, value):
        if not value:
            return "-"
        return f"{value}%" if kind == "percent" else f"₦{value}"

    @admin.display(description=_("fee"))
    def fee_display(self, obj):
        return self._fmt(obj.fee_type, obj.fee_value)

    @admin.display(description=_("discount"))
    def discount_display(self, obj):
        return self._fmt(obj.discount_type, obj.discount_value)

    @admin.display(description=_("cashback"))
    def cashback_display(self, obj):
        return self._fmt(obj.cashback_type, obj.cashback_value)


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "is_active", "position")
    list_editable = ("is_active", "position")
    actions = ("sync_catalog",)

    @admin.action(description=_("Sync the whole catalogue from VTpass"))
    def sync_catalog(self, request, queryset):
        stats = _vtpass().catalog.sync()
        self.message_user(request, _("Catalogue synced: %s") % stats, messages.SUCCESS)


class VariationInline(admin.TabularInline):
    model = Variation
    extra = 0
    fields = ("variation_code", "name", "amount", "fixed_price", "is_active")
    readonly_fields = ("variation_code", "name", "amount", "fixed_price")
    can_delete = False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "service_id", "category", "is_active", "minimum_amount", "maximum_amount",
                    "variations_synced_at")
    list_filter = ("category", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name", "service_id")
    inlines = (VariationInline,)
    actions = ("sync_variations",)

    @admin.action(description=_("Refresh plans for selected services"))
    def sync_variations(self, request, queryset):
        catalog = _vtpass().catalog
        total = sum(catalog.sync_variations(service.service_id) for service in queryset)
        self.message_user(request, _("%d plan(s) refreshed.") % total, messages.SUCCESS)


@admin.register(Variation)
class VariationAdmin(admin.ModelAdmin):
    list_display = ("name", "variation_code", "service", "amount", "fixed_price", "is_active")
    list_filter = ("service__category", "service", "is_active")
    search_fields = ("name", "variation_code")
    list_editable = ("is_active",)


class WalletEntryInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = WalletEntry
    extra = 0
    fields = ("created_at", "direction", "kind", "amount", "balance_after", "reference", "description")
    readonly_fields = fields
    ordering = ("-created_at",)
    show_change_link = True


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "balance", "currency", "is_locked", "updated_at")
    list_filter = ("is_locked", "currency")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "balance", "currency", "uid", "created_at", "updated_at")
    fields = ("user", "balance", "currency", "is_locked", "uid", "created_at", "updated_at")
    inlines = (WalletEntryInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(WalletEntry)
class WalletEntryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("created_at", "wallet", "direction", "kind", "amount", "balance_after", "reference")
    list_filter = ("direction", "kind", "created_at")
    search_fields = ("reference", "wallet__user__username", "transaction__request_id")
    date_hierarchy = "created_at"


@admin.register(Beneficiary)
class BeneficiaryAdmin(admin.ModelAdmin):
    list_display = ("user", "service_id", "billers_code", "nickname", "customer_name", "use_count", "last_used_at")
    list_filter = ("category", "service_id")
    search_fields = ("billers_code", "nickname", "customer_name", "user__username")


@admin.register(WebhookEvent)
class WebhookEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("created_at", "event_type", "request_id", "service_id", "state", "attempts", "remote_ip")
    list_filter = ("event_type", "state")
    search_fields = ("request_id", "service_id")
    actions = ("reprocess",)

    @admin.action(description=_("Reprocess selected events"), permissions=["reprocess"])
    def reprocess(self, request, queryset):
        from vtpass.jobs import process_webhook

        for event in queryset:
            process_webhook(event.payload, event.pk)
        self.message_user(request, _("Events reprocessed."), messages.SUCCESS)

    def has_reprocess_permission(self, request):
        return request.user.is_superuser


@admin.register(SMSMessage)
class SMSMessageAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("created_at", "sender", "recipient_count", "route", "state", "response_code", "purpose")
    list_filter = ("state", "route", "purpose")
    search_fields = ("recipients", "batch_id", "message")
