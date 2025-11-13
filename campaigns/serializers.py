from __future__ import annotations

from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal

from .models import Campaign

User = get_user_model()


class CampaignSerializer(serializers.ModelSerializer):
    remaining_budget = serializers.SerializerMethodField(read_only=True)
    days_left = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Campaign
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        # allow partial updates: fallback to instance values
        start = attrs.get("start_date") or getattr(self.instance, "start_date", None)
        end = attrs.get("end_date") or getattr(self.instance, "end_date", None)
        if start and end and end < start:
            raise serializers.ValidationError("end_date must be on/after start_date.")

        discount_type = attrs.get("discount_type") or getattr(self.instance, "discount_type", None)
        discount_value = attrs.get("discount_value") or getattr(self.instance, "discount_value", None)

        if discount_type == Campaign.DiscountType.PERCENT and discount_value is not None:
            if Decimal(discount_value) < 0 or Decimal(discount_value) > Decimal("100"):
                raise serializers.ValidationError(
                    "For PERCENT type, discount_value must be between 0 and 100."
                )

        if discount_type == Campaign.DiscountType.FLAT and discount_value is not None:
            if Decimal(discount_value) < 0:
                raise serializers.ValidationError(
                    "For FLAT type, discount_value must be >= 0."
                )

        allow_all = attrs.get("allow_all_customers")
        specific = attrs.get("specific_customers")
        if allow_all is False and specific is not None and len(specific) == 0:
            # not fatal, but usually a config mistake
            raise serializers.ValidationError(
                "When allow_all_customers is False, you must specify at least one user in specific_customers."
            )

        return attrs

    def get_remaining_budget(self, obj: Campaign):
        rb = obj.remaining_budget  # property on model
        return None if rb is None else str(rb)

    def get_days_left(self, obj: Campaign):
        return obj.days_left


class CartCheckSerializer(serializers.Serializer):
    customer_id = serializers.IntegerField()
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    delivery = serializers.DecimalField(max_digits=12, decimal_places=2)


class RedeemSerializer(CartCheckSerializer):
    campaign_id = serializers.IntegerField()
