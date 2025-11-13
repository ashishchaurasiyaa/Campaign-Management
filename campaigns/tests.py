from decimal import Decimal
from datetime import timedelta, date

from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Campaign, CampaignBudget, CampaignUsageDaily
from .services import Cart, preview_discount, redeem_discount


class CampaignRulesTest(TestCase):
    """Unit tests to ensure core discount business rules work correctly."""

    def setUp(self):
        self.user = User.objects.create_user(username='u1', password='x')
        today = timezone.now().date()

        # Base campaign used in most tests
        self.camp = Campaign.objects.create(
            name='Test10',
            applies_to=Campaign.AppliesTo.CART,
            discount_type=Campaign.DiscountType.PERCENT,
            discount_value=Decimal('10'),  # 10%
            max_discount_amount=Decimal('200.00'),
            allow_all_customers=True,
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=5),
            run_days_limit=5,
            total_budget_limit=Decimal('1000.00'),
            max_txn_per_customer_per_day=1,
            is_active=True,
        )

    def test_percent_discount_correct(self):
        """10% discount on cart subtotal is calculated correctly."""
        cart = Cart(self.user, Decimal('500.00'), Decimal('50.00'))
        p = preview_discount(self.camp, cart)

        self.assertTrue(p["applicable"])
        self.assertEqual(p["applies_to"], Campaign.AppliesTo.CART)
        self.assertEqual(p["discount_amount"], Decimal('50.00'))  # 10% of 500

    def test_budget_and_usage_update_on_redeem(self):
        """Redeem should update campaign budget and daily usage row."""
        cart = Cart(self.user, Decimal('500.00'), Decimal('50.00'))

        r = redeem_discount(self.camp, cart)
        self.assertTrue(r["applicable"])
        self.assertEqual(r["discount_amount"], Decimal('50.00'))

        # Budget updated
        budget = CampaignBudget.objects.get(campaign=self.camp)
        self.assertEqual(budget.total_discount_given, Decimal('50.00'))

        # Daily usage updated
        usage = CampaignUsageDaily.objects.get(
            campaign=self.camp,
            customer=self.user,
            usage_date=date.today(),
        )
        self.assertEqual(usage.txn_count, 1)

    def test_daily_limit_blocks_second_redeem(self):
        """Second redemption on same day should be blocked (limit=1)."""
        cart = Cart(self.user, Decimal('300.00'), Decimal('20.00'))

        first = redeem_discount(self.camp, cart)
        self.assertTrue(first["applicable"])

        second = redeem_discount(self.camp, cart)
        self.assertFalse(second["applicable"])
        self.assertIn("limit", second["reason"].lower())

    def test_budget_cap_stops_campaign(self):
        """When total budget is fully used, campaign becomes not applicable (budget exhausted)."""
        # Make budget very small and daily limit very high so budget check wins
        self.camp.total_budget_limit = Decimal('40.00')
        self.camp.max_txn_per_customer_per_day = 999
        self.camp.save()

        cart = Cart(self.user, Decimal('500.00'), Decimal('50.00'))

        # First preview: discount capped to remaining budget (40)
        p = preview_discount(self.camp, cart)
        self.assertTrue(p["applicable"])
        self.assertEqual(p["discount_amount"], Decimal('40.00'))

        # Redeem once → consumes full budget
        redeem_discount(self.camp, cart)

        # Now budget exhausted → preview should fail due to budget
        p2 = preview_discount(self.camp, cart)
        self.assertFalse(p2["applicable"])
        self.assertIn("budget", p2["reason"].lower())

    def test_date_window_blocked(self):
        """Campaign outside start/end date should not apply."""
        self.camp.start_date = date.today() + timedelta(days=2)
        self.camp.save()

        cart = Cart(self.user, Decimal('500.00'), Decimal('50.00'))
        p = preview_discount(self.camp, cart)

        self.assertFalse(p["applicable"])
        self.assertIn("inactive", p["reason"].lower())

    def test_targeted_customer_only(self):
        """If allow_all_customers=False, only specific_customers can use the campaign."""
        other_user = User.objects.create_user(username='other', password='x')

        self.camp.allow_all_customers = False
        self.camp.save()
        self.camp.specific_customers.set([self.user])

        # Allowed user
        cart1 = Cart(self.user, Decimal('200.00'), Decimal('20.00'))
        p1 = preview_discount(self.camp, cart1)
        self.assertTrue(p1["applicable"])

        # Not allowed user
        cart2 = Cart(other_user, Decimal('200.00'), Decimal('20.00'))
        p2 = preview_discount(self.camp, cart2)
        self.assertFalse(p2["applicable"])
        self.assertIn("target", p2["reason"].lower())
