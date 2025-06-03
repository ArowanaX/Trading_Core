from rest_framework import serializers
from orders.models import Order
from  currencies.models import Market



class OrderCreateSerializer(serializers.ModelSerializer):
    
    target_market = serializers.CharField()

    class Meta:
        model = Order
        fields = ['id', 'target_market', 'order_type', 'order_side', 'price', 'amount', 'order_state', 'filled_amount', 'created_at', 'updated_at', 'filled_at']
        read_only_fields = ['id', 'order_state', 'filled_amount', 'created_at', 'updated_at', 'filled_at']

    def validate_target_market(self, value):
        try:
            market = Market.objects.get(symbol=value)
            return market
        except Market.DoesNotExist:
            raise serializers.ValidationError(f"Market {value} does not exist.")



class CancelOrderSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()

    def validate_order_id(self, value):
        try:
            order = Order.objects.get(id=value, order_state__in=[Order.OrderState.WAITING, Order.OrderState.PARTIALLY_FILLED])
            return order
        except Order.DoesNotExist:
            raise serializers.ValidationError(f"Order {value} is not valid or cannot be canceled.")