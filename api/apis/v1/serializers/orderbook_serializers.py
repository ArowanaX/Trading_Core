from rest_framework import serializers
from currencies.models import Market

class OrderBookSerializer(serializers.Serializer):
    market_symbol = serializers.CharField(max_length=17)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=10)

    def validate_market_symbol(self, value):
        try:
            Market.objects.get(symbol=value)
            return value
        except Market.DoesNotExist:
            raise serializers.ValidationError(f"Market {value} does not exist.")

class OrderBookResponseSerializer(serializers.Serializer):
    price = serializers.FloatField()
    amount = serializers.FloatField() 