from rest_framework import generics
from currencies.models import Market
from ..serializers.market_serializers import MarketSerializer


class MarketListCreateView(generics.ListCreateAPIView):
    # Get list of Market and create new
    queryset = Market.objects.all()
    serializer_class = MarketSerializer
