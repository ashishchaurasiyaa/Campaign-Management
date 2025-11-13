from __future__ import annotations

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import Campaign
from .serializers import CampaignSerializer, CartCheckSerializer, RedeemSerializer
from .services import Cart, preview_discount, redeem_discount

User = get_user_model()


class IsAdminOrReadOnly(permissions.BasePermission):
    """Allow read-only for everyone, write for staff."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


@extend_schema(tags=["Campaigns"])
class CampaignViewSet(viewsets.ModelViewSet):
    """
    CRUD + functional endpoints for managing discount campaigns.
    Includes:
    - /campaigns/available/ → check eligible discounts for cart
    - /campaigns/redeem/ → apply a discount and update usage/budget
    """
    queryset = Campaign.objects.all().order_by("-created_at")
    serializer_class = CampaignSerializer
    permission_classes = [IsAdminOrReadOnly]


    def _collect_cart(self, request):
        """Read cart parameters from GET query or POST body."""
        if request.method == "GET":
            try:
                customer_id = int(request.query_params.get("customer_id"))
                subtotal = request.query_params.get("subtotal")
                delivery = request.query_params.get("delivery")
                if not (customer_id and subtotal and delivery):
                    raise ValueError
            except Exception:
                return None, Response(
                    {"detail": "Provide customer_id, subtotal, and delivery as query params."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            user = get_object_or_404(User, pk=customer_id)
            return Cart(user, subtotal, delivery), None

        payload = CartCheckSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        d = payload.validated_data

        user = get_object_or_404(User, pk=d["customer_id"])

        return Cart(user, d["subtotal"], d["delivery"]), None

    @extend_schema(
        parameters=[
            OpenApiParameter("customer_id", OpenApiTypes.INT, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("subtotal", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=False),
            OpenApiParameter("delivery", OpenApiTypes.NUMBER, OpenApiParameter.QUERY, required=False),
        ],
        request=CartCheckSerializer,
        responses={200: OpenApiTypes.OBJECT},
        description="List all campaigns currently applicable to a given cart (GET is public; POST requires auth).",
    )
    @action(detail=False, methods=["get", "post"], url_path="available")
    def available(self, request):
        cart, error = self._collect_cart(request)
        if error:
            return error

        applicable = []
        for c in self.get_queryset().filter(is_active=True):
            prev = preview_discount(c, cart)
            if prev.get("applicable"):
                applicable.append({
                    "campaign_id": c.id,
                    "campaign_name": c.name,
                    "applies_to": prev["applies_to"],
                    "discount_amount": str(prev["discount_amount"]),
                    "discount_type": c.discount_type,
                    "discount_value": str(c.discount_value),
                })

        return Response({"available_campaigns": applicable}, status=status.HTTP_200_OK)

    @extend_schema(
        request=RedeemSerializer,
        responses={200: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        description="Redeem a campaign discount (auth required). Atomic update of daily usage and budget with row locks.",
    )
    @action(detail=False, methods=["post"], url_path="redeem")
    def redeem(self, request):
        payload = RedeemSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        d = payload.validated_data

        user = get_object_or_404(User, pk=d["customer_id"])

        campaign = get_object_or_404(Campaign, pk=d["campaign_id"])
        cart = Cart(user, d["subtotal"], d["delivery"])

        result = redeem_discount(campaign, cart)
        if "discount_amount" in result:
            result["discount_amount"] = str(result["discount_amount"])

        code = status.HTTP_200_OK if result.get("applicable") else status.HTTP_400_BAD_REQUEST
        return Response(result, status=code)
