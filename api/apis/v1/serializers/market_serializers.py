from rest_framework import serializers
from currencies.models import Market



class MarketSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Market
        fields = ['id', 'base_currency', 'quote_currency', 'fee']
