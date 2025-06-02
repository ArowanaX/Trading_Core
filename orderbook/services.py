import redis
import json
# import logging
from decimal import Decimal
from typing import Dict
from collections import defaultdict
from orders.models import Order
from currencies.models import Market

# logger = logging.getLogger(__name__)

class OrderBookService:
    """
    This class is responsible for maintaining the order book
    and syncing between Redis and the main database.
    """
    
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.default_limit = 10
    
    def get_order_book(self, market_symbol: str, limit: int = None):
        """
        Retrieve the order book for a specific market from Redis.
        If not present, sync from postgres.
        """
        if limit is None:
            limit = self.default_limit
            
        try:
            # Check if market exists
            if not self._market_exists(market_symbol):
                raise ValueError(f"Market {market_symbol} does not exist")
            
            # Get from Redis
            sell = self._get_sell_from_redis(market_symbol, limit)
            buy = self._get_buy_from_redis(market_symbol, limit)
            
            # If Redis is empty, sync with postgres
            if not sell and not buy:
                self.sync_order_book(market_symbol)
                sell = self._get_sell_from_redis(market_symbol, limit)
                buy = self._get_buy_from_redis(market_symbol, limit)
            
            return {
                "market_symbol": market_symbol,
                "sell": sell,
                "buy": buy,
                "timestamp": self._get_current_timestamp()
            }
            
        except Exception as e:
            print(f"Error getting order book for {market_symbol}: {str(e)}")
            # In case of error, read from postgres
            return self._get_order_book_from_db(market_symbol, limit)
    
    def update_order_book(self, market_symbol: str):
        """
        Update the order book in Redis based on changes in postgres.
        This method is called after each order match.
        
        Args:
            market_symbol: Market symbol
        """
        try:
            if not self._market_exists(market_symbol):
                print(f"Market {market_symbol} does not exist")
                return
            
            # Clear current order book
            self._clear_order_book_cache(market_symbol)
            
            # Rebuild from postgres
            self._rebuild_order_book_from_db(market_symbol)
            
            # Set last update time
            self._set_last_update_time(market_symbol)
            
            print(f"Order book updated for {market_symbol}")
            
        except Exception as e:
            print(f"Error updating order book for {market_symbol}: {str(e)}")
    
    def sync_order_book(self, market_symbol: str):
        """
        Fully synchronize the order book between Redis and postgres.
        This method runs in tasks or at specific intervals.
        """
        try:
            print(f"Starting full sync for order book {market_symbol}")
            
            if not self._market_exists(market_symbol):
                print(f"Market {market_symbol} does not exist")
                return
            
            # Lock to prevent race conditions
            lock_key = f"sync_lock:{market_symbol}"
            
            if self.redis_client.set(lock_key, "1", nx=True, ex=30):  # 30-second lock
                try:
                    # Clear Redis
                    self._clear_order_book_cache(market_symbol)
                    
                    # Fully rebuild from postgres
                    self._rebuild_order_book_from_db(market_symbol)
                    
                    # Set last sync time
                    self._set_last_sync_time(market_symbol)
                    
                    print(f"Order book sync completed for {market_symbol}")
                    
                finally:
                    # Release the lock
                    self.redis_client.delete(lock_key)
            else:
                print(f"Sync already in progress for {market_symbol}")
                
        except Exception as e:
            print(f"Error syncing order book for {market_symbol}: {str(e)}")
    
    def _get_sell_from_redis(self, market_symbol: str, limit: int):

        #create redis key
        redis_key = f"orderbook:{market_symbol}:sell"
        orders_data = self.redis_client.zrange(redis_key, 0, limit - 1, withscores=True)
        
        # Aggregate orders with the same price
        price_groups = defaultdict(Decimal)
        
        for order_json, score in orders_data:
            order_data = json.loads(order_json)
            price = Decimal(order_data['price'])
            amount = Decimal(order_data['amount'])
            price_groups[price] += amount
        
        # Convert to list and sort by price (ascending)
        sell = []
        for price in sorted(price_groups.keys()):
            sell.append({
                "price": float(price),
                "amount": float(price_groups[price])
            })
        
        return sell[:limit]
    
    def _get_buy_from_redis(self, market_symbol: str, limit: int):
        
        #create redis key
        redis_key = f"orderbook:{market_symbol}:buy"
        orders_data = self.redis_client.zrange(redis_key, 0, limit - 1, withscores=True)
        
        # Aggregate orders with the same price
        price_groups = defaultdict(Decimal)
        
        for order_json, score in orders_data:
            order_data = json.loads(order_json)
            price = Decimal(order_data['price'])
            amount = Decimal(order_data['amount'])
            price_groups[price] += amount
        
        # Convert to list and sort by price (descending)
        buy = []
        for price in sorted(price_groups.keys(), reverse=True):
            buy.append({
                "price": float(price),
                "amount": float(price_groups[price])  
            })
        
        return buy[:limit]
    
    def _get_order_book_from_db(self, market_symbol: str, limit: int) -> Dict:
        """
        Retrieve order book directly from postgres (fallback).
        """
        try:
            market = Market.objects.get(symbol=market_symbol)
            
            # Sell orders - ascending price
            sell_orders = Order.objects.filter(
                target_market=market,
                order_side=Order.OrderSide.SELL,
                order_state__in=[Order.OrderState.WAITING, Order.OrderState.PARTIALLY_FILLED],
                remaining_amount__gt=0
            ).values('price', 'remaining_amount').order_by('price', 'created_at')
            
            # Buy orders - descending price  
            buy_orders = Order.objects.filter(
                target_market=market,
                order_side=Order.OrderSide.BUY,
                order_state__in=[Order.OrderState.WAITING, Order.OrderState.PARTIALLY_FILLED],
                remaining_amount__gt=0
            ).values('price', 'remaining_amount').order_by('-price', 'created_at')
            
            # Aggregate sell orders
            sell_groups = defaultdict(Decimal)
            for order in sell_orders:
                sell_groups[order['price']] += order['remaining_amount']
            
            sell = []
            for price in sorted(sell_groups.keys()):
                sell.append({
                    "price": float(price),
                    "amount": float(sell_groups[price])
                })
            
            # Aggregate buy orders
            buy_groups = defaultdict(Decimal)
            for order in buy_orders:
                buy_groups[order['price']] += order['remaining_amount']
            
            buy = []
            for price in sorted(buy_groups.keys(), reverse=True):
                buy.append({
                    "price": float(price),
                    "amount": float(buy_groups[price])
                })
            
            return {
                "market_symbol": market_symbol,
                "sell": sell[:limit],
                "buy": buy[:limit],
                "timestamp": self._get_current_timestamp(),
                "source": "database"
            }
            
        except Market.DoesNotExist:
            print(f"Market {market_symbol} not found in database")
            return {
                "market_symbol": market_symbol,
                "sell": [],
                "buy": [],
                "timestamp": self._get_current_timestamp(),
                "error": "Market not found"
            }
    
    def _rebuild_order_book_from_db(self, market_symbol: str):
        """
        Fully rebuild the order book in Redis from postgres.
        """
        try:
            market = Market.objects.get(symbol=market_symbol)
            
            # Retrieve active orders
            active_orders = Order.objects.filter(
                target_market=market,
                order_state__in=[Order.OrderState.WAITING, Order.OrderState.PARTIALLY_FILLED],
                remaining_amount__gt=0
            ).select_related('target_market')
            
            # Add to Redis
            for order in active_orders:
                self._add_order_to_redis(order)
                
        except Market.DoesNotExist:
            print(f"Market {market_symbol} not found")
        except Exception as e:
            print(f"Error rebuilding order book for {market_symbol}: {str(e)}")
    
    def _add_order_to_redis(self, order: Order):
        """
        Add a single order to Redis.
        """
        try:
            market_symbol = order.target_market.symbol
            side = order.order_side
            
            order_data = {
                'id': order.id,
                'price': str(order.price),
                'amount': str(order.remaining_amount),
                'created_at': order.created_at.isoformat()
            }
            
            redis_key = f"orderbook:{market_symbol}:{side}"
            
            # Determine score based on order type
            if side == Order.OrderSide.BUY:
                # Buy: higher price has priority (negative for descending order)
                score = float(-order.price)
            else:
                # Sell: lower price has priority
                score = float(order.price)
            
            self.redis_client.zadd(redis_key, {json.dumps(order_data): score})
            
        except Exception as e:
            print(f"Error adding order {order.id} to Redis: {str(e)}")
    
    def _clear_order_book_cache(self, market_symbol: str):
        """
        Clear the order book from Redis.
        """
        try:
            buy_key = f"orderbook:{market_symbol}:buy"
            sell_key = f"orderbook:{market_symbol}:sell"
     
            self.redis_client.delete(buy_key)
            self.redis_client.delete(sell_key)
            
        except Exception as e:
            print(f"Error clearing order book cache for {market_symbol}: {str(e)}")
    
    def _market_exists(self, market_symbol: str):
        """
        Check if the market exists.
        """
        try:
            Market.objects.get(symbol=market_symbol)
            return True
        except Market.DoesNotExist:
            return False
    
    def _set_last_update_time(self, market_symbol: str):
        """
        Set the last update time.
        """
        key = f"orderbook:last_update:{market_symbol}"
        self.redis_client.set(key, self._get_current_timestamp())
    
    def _set_last_sync_time(self, market_symbol: str):
        """
        Set the last sync time.
        """
        key = f"orderbook:last_sync:{market_symbol}"
        self.redis_client.set(key, self._get_current_timestamp())
    
    def _get_current_timestamp(self) -> str:
        """
        Get the current timestamp.
        """
        from django.utils import timezone
        return timezone.now().isoformat()
    
    def get_order_book_stats(self, market_symbol: str) -> Dict:
        """
        Retrieve order book statistics (for monitoring).
        """
        try:
            buy_key = f"orderbook:{market_symbol}:buy"
            sell_key = f"orderbook:{market_symbol}:sell"
            
            buy_count = self.redis_client.zcard(buy_key)
            sell_count = self.redis_client.zcard(sell_key)
            
            last_update = self.redis_client.get(f"orderbook:last_update:{market_symbol}")
            last_sync = self.redis_client.get(f"orderbook:last_sync:{market_symbol}")
            
            return {
                "market_symbol": market_symbol,
                "buy_orders_count": buy_count,
                "sell_orders_count": sell_count,
                "last_update": last_update,
                "last_sync": last_sync,
                "total_orders": buy_count + sell_count
            }
            
        except Exception as e:
            print(f"Error getting order book stats for {market_symbol}: {str(e)}")
            return {
                "market_symbol": market_symbol,
                "error": str(e)
            }

order_book_service = OrderBookService()