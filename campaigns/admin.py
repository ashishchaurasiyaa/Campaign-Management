from django.contrib import admin
from .models import Campaign, CampaignBudget, CampaignUsageDaily


class CampaignBudgetInline(admin.StackedInline):
    model = CampaignBudget
    extra = 0
    can_delete = False
    readonly_fields = ("total_discount_given", "created_at", "updated_at")


class CampaignUsageDailyInline(admin.TabularInline):
    model = CampaignUsageDaily
    extra = 0
    can_delete = False
    readonly_fields = ("usage_date", "customer", "txn_count", "created_at", "updated_at")
    ordering = ("-usage_date",)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "applies_to",
        "discount_type",
        "discount_value",
        "max_discount_amount",
        "allow_all_customers",
        "is_active",
        "start_date",
        "end_date",
        "remaining_budget_display",
        "days_left_display",
    )
    list_filter = (
        "applies_to",
        "discount_type",
        "is_active",
        "allow_all_customers",
        "start_date",
        "end_date",
    )
    search_fields = ("name", "description")
    ordering = ("-created_at",)
    filter_horizontal = ("specific_customers",)
    inlines = [CampaignBudgetInline, CampaignUsageDailyInline]

    fieldsets = (
        ("Basic Info", {
            "fields": (
                "name",
                "description",
                ("applies_to", "discount_type"),
                ("discount_value", "max_discount_amount"),
            )
        }),
        ("Customer Targeting", {
            "fields": ("allow_all_customers", "specific_customers")
        }),
        ("Schedule & Limits", {
            "fields": (
                ("start_date", "end_date"),
                ("run_days_limit", "total_budget_limit"),
                "max_txn_per_customer_per_day",
            )
        }),
        ("Status", {"fields": ("is_active",)}),
    )

    # computed columns
    @admin.display(description="Remaining Budget")
    def remaining_budget_display(self, obj: Campaign):
        if obj.total_budget_limit is None:
            return "Unlimited"
        return obj.remaining_budget

    @admin.display(description="Days Left")
    def days_left_display(self, obj: Campaign):
        v = obj.days_left
        return "—" if v is None else v


@admin.register(CampaignBudget)
class CampaignBudgetAdmin(admin.ModelAdmin):
    list_display = ("campaign", "total_discount_given", "created_at", "updated_at")
    search_fields = ("campaign__name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(CampaignUsageDaily)
class CampaignUsageDailyAdmin(admin.ModelAdmin):
    list_display = ("campaign", "customer", "usage_date", "txn_count", "created_at")
    list_filter = ("usage_date", "campaign")
    search_fields = ("campaign__name", "customer__username")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-usage_date",)
