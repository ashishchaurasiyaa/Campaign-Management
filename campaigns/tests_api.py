from datetime import timedelta

from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient


class CampaignIntegrationAPITests(APITestCase):
    """
    End-to-end test of:
    - Admin CRUD on /api/campaigns/
    - /api/campaigns/available/ (GET + POST)
    - /api/campaigns/redeem/
    """

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", is_staff=True
        )
        self.client_admin = APIClient()
        self.client_admin.force_authenticate(self.admin)

        self.customer = User.objects.create_user(username="cust1", password="x")

        self.list_url = reverse("campaign-list")
        self.available_url = reverse("campaign-available")
        self.redeem_url = reverse("campaign-redeem")

        today = timezone.now().date()
        self.campaign_payload = {
            "name": "ITEST CART 20%",
            "description": "integration test campaign",
            "applies_to": "CART",
            "discount_type": "PERCENT",
            "discount_value": "20",          # 20%
            "max_discount_amount": "200.00",
            "allow_all_customers": True,
            "start_date": str(today - timedelta(days=1)),
            "end_date": str(today + timedelta(days=10)),
            "run_days_limit": 5,
            "total_budget_limit": "500.00",
            "max_txn_per_customer_per_day": 1,
            "is_active": True,
        }

    def test_crud_available_and_redeem_flow(self):
        create_res = self.client_admin.post(self.list_url, self.campaign_payload, format="json")
        self.assertEqual(create_res.status_code, 201, create_res.data)
        camp_id = create_res.data["id"]

        list_res = self.client_admin.get(self.list_url)
        self.assertEqual(list_res.status_code, 200)

        get_res = self.client_admin.get(
            self.available_url,
            {"customer_id": self.customer.id, "subtotal": "1200.00", "delivery": "80.00"},
        )
        self.assertEqual(get_res.status_code, 200, get_res.data)
        self.assertTrue(len(get_res.data["available_campaigns"]) >= 1)

        post_res = self.client_admin.post(
            self.available_url,
            {
                "customer_id": self.customer.id,
                "subtotal": "1200.00",
                "delivery": "80.00",
            },
            format="json",
        )
        self.assertEqual(post_res.status_code, 200, post_res.data)
        self.assertTrue(len(post_res.data["available_campaigns"]) >= 1)

        redeem_ok = self.client_admin.post(
            self.redeem_url,
            {
                "campaign_id": camp_id,
                "customer_id": self.customer.id,
                "subtotal": "1200.00",
                "delivery": "80.00",
            },
            format="json",
        )
        self.assertEqual(redeem_ok.status_code, 200, redeem_ok.data)
        self.assertTrue(redeem_ok.data["applicable"])
        self.assertIn("discount_amount", redeem_ok.data)

        redeem_cap = self.client_admin.post(
            self.redeem_url,
            {
                "campaign_id": camp_id,
                "customer_id": self.customer.id,
                "subtotal": "1200.00",
                "delivery": "80.00",
            },
            format="json",
        )
        self.assertEqual(redeem_cap.status_code, 400, redeem_cap.data)
        self.assertFalse(redeem_cap.data["applicable"])
        self.assertIn("limit", redeem_cap.data["reason"].lower())

        patch_res = self.client_admin.patch(
            reverse("campaign-detail", args=[camp_id]),
            {"is_active": False},
            format="json",
        )
        self.assertEqual(patch_res.status_code, 200)
        self.assertEqual(patch_res.data["is_active"], False)

        del_res = self.client_admin.delete(
            reverse("campaign-detail", args=[camp_id])
        )
        self.assertIn(del_res.status_code, (200, 204))