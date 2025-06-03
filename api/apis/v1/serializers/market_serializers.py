from rest_framework import serializers
from currencies.models import Market



class MarketSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Market
        fields = ['id', 'base_currency', 'quote_currency', 'fee']

    def validate(self, data):
        if data['base_currency'] == data['quote_currency']:
            raise serializers.ValidationError("Cant create market with same base and quote currency.!")
        return data