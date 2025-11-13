from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Optional, Dict, Any
from datetime import date

from django.db import transaction

from .models import Campaign, CampaignBudget, CampaignUsageDaily


class Cart:
    """Lightweight cart DTO used by preview/redeem services."""
    def __init__(self, customer, subtotal: Decimal, delivery: Decimal):
        self.customer = customer
        self.subtotal = Decimal(subtotal)
        self.delivery = Decimal(delivery)


def _eligible_customer(c: Campaign, user) -> bool:
    """True if the user is allowed to use campaign c."""
    if not c.allow_all_customers:
        return c.specific_customers.filter(pk=getattr(user, "pk", None)).exists()
    return True


def _budget_remaining(c: Campaign) -> Optional[Decimal]:
    """Remaining budget for campaign c, or None if unlimited."""
    if not c.total_budget_limit:
        return None
    budget, _ = CampaignBudget.objects.get_or_create(campaign=c)
    return Decimal(c.total_budget_limit) - budget.total_discount_given


def _per_day_txn_left(c: Campaign, user) -> int:
    """How many redemptions are left for user today on campaign c."""
    record, _ = CampaignUsageDaily.objects.get_or_create(
        campaign=c, customer=user, usage_date=date.today()
    )
    return max(0, c.max_txn_per_customer_per_day - record.txn_count)


def _compute_raw_discount(c: Campaign, amount: Decimal) -> Decimal:
    """Compute raw discount (pre-budget-cap) based on campaign rule."""
    amount = max(Decimal("0.00"), Decimal(amount))
    if c.discount_type == Campaign.DiscountType.PERCENT:
        disc = (amount * Decimal(c.discount_value)) / Decimal(100)
    else:  # FLAT
        disc = Decimal(c.discount_value)

    if c.max_discount_amount:
        disc = min(disc, Decimal(c.max_discount_amount))

    # Normalize to 2 dp, never negative
    return max(Decimal("0.00"), disc.quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def preview_discount(campaign: Campaign, cart: Cart) -> Dict[str, Any]:
    """
    Check if a campaign applies to the given cart and compute the discount (without mutating state).

    Returns a dict:
      {
        'applicable': bool,
        'reason': str (present when applicable is False),
        'discount_amount': Decimal,
        'applies_to': 'CART' | 'DELIVERY'
      }
    """
    c = campaign
    reason = None

    # Global checks: status, window, run-days limit
    if not (c.is_active and c.is_within_date_window() and not c.days_exhausted()):
        reason = "Inactive or outside schedule."
    elif not _eligible_customer(c, cart.customer):
        reason = "Customer not targeted."
    elif _per_day_txn_left(c, cart.customer) <= 0:
        reason = "Daily usage limit reached."
    else:
        base = cart.subtotal if c.applies_to == c.AppliesTo.CART else cart.delivery
        if base <= 0:
            reason = "Nothing to discount."
        else:
            disc = _compute_raw_discount(c, base)

            # Cap by remaining budget if any
            remaining = _budget_remaining(c)
            if remaining is not None:
                if remaining <= 0:
                    reason = "Budget exhausted."
                else:
                    disc = min(disc, remaining)

            if not reason and disc > 0:
                return {
                    "applicable": True,
                    "applies_to": c.applies_to,
                    "discount_amount": disc,
                }

    return {
        "applicable": False,
        "reason": reason or "Not applicable.",
        "discount_amount": Decimal("0.00"),
        "applies_to": c.applies_to,
    }


@transaction.atomic
def redeem_discount(campaign: Campaign, cart: Cart) -> Dict[str, Any]:
    """
    Apply and persist a redemption atomically:
      - re-validates with preview
      - increments daily usage (with SELECT ... FOR UPDATE)
      - increments total budget used (if capped)
    """
    prev = preview_discount(campaign, cart)
    if not prev.get("applicable"):
        return prev

    disc = prev["discount_amount"]

    # Lock the usage row for (campaign, customer, today)
    daily, _ = CampaignUsageDaily.objects.select_for_update().get_or_create(
        campaign=campaign, customer=cart.customer, usage_date=date.today()
    )
    if daily.txn_count >= campaign.max_txn_per_customer_per_day:
        return {"applicable": False, "reason": "Race: daily limit reached."}

    daily.txn_count += 1
    daily.save()

    # Update budget if capped; lock the row to avoid races
    if campaign.total_budget_limit:
        budget, _ = CampaignBudget.objects.select_for_update().get_or_create(campaign=campaign)
        budget.total_discount_given += disc
        budget.save()

    return {
        "applicable": True,
        "discount_amount": disc,
        "applies_to": campaign.applies_to,
    }
