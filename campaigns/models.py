from django.conf import settings
from django.db import models
from decimal import Decimal
from datetime import date, timedelta


class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Campaign(TimeStamped):
    class AppliesTo(models.TextChoices):
        CART = "CART", "Cart Total"
        DELIVERY = "DELIVERY", "Delivery Charge"

    class DiscountType(models.TextChoices):
        PERCENT = "PERCENT", "Percent"
        FLAT = "FLAT", "Flat Amount"

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    applies_to = models.CharField(
        max_length=16, choices=AppliesTo.choices, default=AppliesTo.CART
    )
    discount_type = models.CharField(
        max_length=16, choices=DiscountType.choices, default=DiscountType.PERCENT
    )
    # percent value for PERCENT type | absolute for FLAT type
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)

    # optional cap per redemption
    max_discount_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )

    # targeting
    allow_all_customers = models.BooleanField(default=True)
    specific_customers = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="allowed_campaigns"
    )

    # schedule
    start_date = models.DateField()
    end_date = models.DateField()
    run_days_limit = models.PositiveIntegerField(null=True, blank=True)

    # stop when total budget is reached
    total_budget_limit = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    # per-customer per-day cap
    max_txn_per_customer_per_day = models.PositiveIntegerField(default=999)

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            # end >= start
            models.CheckConstraint(
                name="campaign_end_after_start",
                check=models.Q(end_date__gte=models.F("start_date")),
            ),
            # percent must be 0..100, flat must be >=0
            models.CheckConstraint(
                name="campaign_discount_value_valid",
                check=(
                    models.Q(
                        discount_type="PERCENT",
                        discount_value__gte=Decimal("0.00"),
                        discount_value__lte=Decimal("100.00"),
                    )
                    | models.Q(
                        discount_type="FLAT",
                        discount_value__gte=Decimal("0.00"),
                    )
                ),
            ),
        ]
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} · {self.applies_to} · {self.discount_type}"

    # business helpers
    def days_exhausted(self) -> bool:
        if not self.run_days_limit:
            return False
        return date.today() > (self.start_date + timedelta(days=self.run_days_limit - 1))

    def is_within_date_window(self) -> bool:
        today = date.today()
        return self.start_date <= today <= self.end_date

    @property
    def remaining_budget(self) -> Decimal | None:
        """Convenience for admin – None if unlimited."""
        if self.total_budget_limit is None:
            return None
        if not hasattr(self, "budget"):
            return Decimal(self.total_budget_limit)
        return Decimal(self.total_budget_limit) - self.budget.total_discount_given

    @property
    def days_left(self) -> int | None:
        """Remaining days considering run_days_limit + end_date; None if not started/ended or unlimited."""
        today = date.today()
        if today > self.end_date:
            return 0
        natural_left = (self.end_date - today).days + 1
        if self.run_days_limit:
            started_span = (today - self.start_date).days + 1
            # days used capped at run_days_limit
            used = max(0, started_span)
            left_by_run = max(0, self.run_days_limit - used)
            return min(natural_left, left_by_run)
        return max(0, natural_left)


class CampaignBudget(TimeStamped):
    """Tracks cumulative discount paid out by a campaign."""
    campaign = models.OneToOneField(
        Campaign, on_delete=models.CASCADE, related_name="budget"
    )
    total_discount_given = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        verbose_name_plural = "Campaign budgets"

    def __str__(self) -> str:
        return f"Budget • {self.campaign.name} • used={self.total_discount_given}"


class CampaignUsageDaily(TimeStamped):
    """Per-customer per-day usage (transaction count)."""
    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="daily_usages"
    )
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    usage_date = models.DateField(db_index=True)
    txn_count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("campaign", "customer", "usage_date")
        verbose_name_plural = "Campaign daily usage"
        indexes = [models.Index(fields=["campaign", "customer", "usage_date"])]

    def __str__(self) -> str:
        return f"{self.usage_date} • {self.customer} • {self.campaign.name} • {self.txn_count} txn"
