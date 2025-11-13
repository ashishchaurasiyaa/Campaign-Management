from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from random import randint, choice

from campaigns.models import Campaign, CampaignBudget, CampaignUsageDaily


class Command(BaseCommand):
    help = "Seed ~50 campaigns + 2 test users for development/testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fresh",
            action="store_true",
            help="Delete existing campaigns/budgets/usages before seeding",
        )
        parser.add_argument(
            "--no-users",
            action="store_true",
            help="Do not create test users (only campaigns)",
        )

    def handle(self, *args, **opts):
        fresh: bool = opts["fresh"]
        no_users: bool = opts["no_users"]

        # ---------------- CLEAN OLD DATA ----------------
        if fresh:
            self.stdout.write(self.style.WARNING("Cleaning old campaign data…"))
            CampaignBudget.objects.all().delete()
            CampaignUsageDaily.objects.all().delete()
            Campaign.objects.all().delete()

        # ---------------- USERS ----------------
        users = []
        if not no_users:
            for username in ("customer1", "customer2"):
                u, created = User.objects.get_or_create(username=username)
                if created:
                    u.set_password("pass1234")
                    u.save()
                users.append(u)

            self.stdout.write(
                self.style.SUCCESS(f"Ensured {len(users)} test users (password: pass1234)")
            )
        else:
            self.stdout.write(self.style.WARNING("Skipping user creation (--no-users)"))

        today = timezone.now().date()

        # ---------------- 3 DETERMINISTIC CAMPAIGNS ----------------
        deterministic_campaigns = [
            Campaign.objects.create(
                name="Cart 10% OFF",
                description="10% discount on cart subtotal for all customers.",
                applies_to="CART",
                discount_type="PERCENT",
                discount_value=Decimal("10.00"),
                max_discount_amount=Decimal("200.00"),
                allow_all_customers=True,
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=30),
                run_days_limit=15,
                total_budget_limit=Decimal("1000.00"),
                max_txn_per_customer_per_day=2,
                is_active=True,
            ),
            Campaign.objects.create(
                name="Delivery FLAT 50",
                description="Flat 50 discount on delivery charges.",
                applies_to="DELIVERY",
                discount_type="FLAT",
                discount_value=Decimal("50.00"),
                max_discount_amount=Decimal("50.00"),
                allow_all_customers=True,
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=30),
                run_days_limit=None,
                total_budget_limit=Decimal("500.00"),
                max_txn_per_customer_per_day=3,
                is_active=True,
            ),
            Campaign.objects.create(
                name="Targeted Cart 20%",
                description="20% discount only for customer1.",
                applies_to="CART",
                discount_type="PERCENT",
                discount_value=Decimal("20.00"),
                max_discount_amount=Decimal("300.00"),
                allow_all_customers=False,
                start_date=today - timedelta(days=1),
                end_date=today + timedelta(days=10),
                run_days_limit=5,
                total_budget_limit=Decimal("800.00"),
                max_txn_per_customer_per_day=1,
                is_active=True,
            ),
        ]

        # Targeted campaign → assign specific customer
        if users:
            deterministic_campaigns[2].specific_customers.add(users[0])
            deterministic_campaigns[2].save()

        # ---------------- 47 RANDOM CAMPAIGNS ----------------
        name_chunks = ["Mega", "Super", "Deal", "Fest", "Saver", "Prime", "Ultra", "Smart"]
        total_created = 3

        for i in range(47):  # total = 3 + 47 = 50
            name = f"{choice(name_chunks)} Campaign {i+1}"

            applies_to = choice(["CART", "DELIVERY"])
            discount_type = choice(["PERCENT", "FLAT"])

            if discount_type == "PERCENT":
                discount_value = Decimal(randint(5, 40))  # 5%–40%
            else:
                discount_value = Decimal(randint(20, 200))  # flat 20–200

            camp = Campaign.objects.create(
                name=name,
                description="Auto-generated sample campaign",
                applies_to=applies_to,
                discount_type=discount_type,
                discount_value=discount_value,
                max_discount_amount=Decimal(choice([100, 150, 200, 300])),
                allow_all_customers=True,
                start_date=today - timedelta(days=randint(0, 3)),
                end_date=today + timedelta(days=randint(10, 40)),
                run_days_limit=choice([None, 5, 7, 10]),
                total_budget_limit=Decimal(choice([500, 1000, 2000, 5000])),
                max_txn_per_customer_per_day=choice([1, 2, 3]),
                is_active=True,
            )

            total_created += 1

        # ---------------- OUTPUT ----------------
        self.stdout.write(self.style.SUCCESS(f"Total seeded campaigns: {total_created}"))
        self.stdout.write(self.style.SUCCESS("Open /admin or /api/docs to test all methods now."))
