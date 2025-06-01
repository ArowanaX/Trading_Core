from currencies.models import Market
from .models import Order
from django.db import transaction 
from redis import Redis
from django.conf import settings


class MatchingEngine:
    def __init__(self, market_symbol):
        self.market = Market.objects.get(symbol=market_symbol)
        self.redis = Redis.from_url(settings.REDIS_URL)

    def match_order(self, order):
        with transaction.atomic():
         
            order = Order.objects.select_for_update().get(id=order.id)
            key = f"order_book:{self.market.symbol}:{'sell' if order.order_side == 'buy' else 'buy'}"
            opposite_orders = self.redis.zrange(key, 0, 10)
  