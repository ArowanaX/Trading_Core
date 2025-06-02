import redis
import json
import logging
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from orders.models import Order, Trade
from orderbook.services import order_book_service

logger = logging.getLogger(__name__)

class MatchingEngine:
    
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
    def process_order(self, order_id: int):
        """
        main process for all of orders 
        """
        try:
            with transaction.atomic():
                order = Order.objects.get(id=order_id)
                if order.order_state != Order.OrderState.WAITING:
                    return {"status": "error", "message": "Order is not in waiting state"}
                
                # calculate remaining_amount
                order.remaining_amount = order.amount - (order.filled_amount or Decimal('0'))
                order.save()
                
                if order.order_type == Order.OrderType.MARKET:
                    return self._process_market_order(order)
                else:
                    return self._process_limit_order(order)
                    
        except Order.DoesNotExist:
            print(f"Order {order_id} not found")
            return {"status": "error", "message": "Order not found"}
        except Exception as e:
            print(f"Error processing order {order_id}: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _process_market_order(self, order: Order):
        """
        process for market orders (order filled with best exist price in momment)
        """
        matching_orders = self._find_matching_orders(order)
        
        if not matching_orders:
            order.order_state = Order.OrderState.ERROR
            order.save()
            return {"status": "no_match", "message": "No matching orders found for market order"}
        
        total_matched = Decimal('0')
        
        for matching_order in matching_orders:
            if order.remaining_amount <= 0:
                break
                
            matched_amount = min(order.remaining_amount, matching_order.remaining_amount)
            
            #create trade
            trade = self._create_trade(order, matching_order, matched_amount)
      
            # update orders amount
            self._update_order_amounts(order, matching_order, matched_amount)
            
            total_matched += matched_amount

        # update order state based on remaining price
        self._update_order_state(order)

        # update order book for display updated data
        self._update_order_book(order)
        
        return {
            "status": "processed",
            "matched_amount": str(total_matched),
            "order_state": order.order_state
        }
    
    def _process_limit_order(self, order: Order):
        """
        process for limit orders (execute when find a suitable order)
        """
        matching_orders = self._find_matching_orders(order)
        total_matched = Decimal('0')
        for matching_order in matching_orders:
            if order.remaining_amount <= 0:
                break
                
            # manage price for limit order
            if not self._price_matches_limit_order(order, matching_order):
                break
                
            matched_amount = min(order.remaining_amount, matching_order.remaining_amount)
            
            # create trade
            trade = self._create_trade(order, matching_order, matched_amount)
            
            # update order amount after trade
            self._update_order_amounts(order, matching_order, matched_amount)
            
            total_matched += matched_amount
        
        # update order state after based on remaining price
        self._update_order_state(order)
        
        # include remaining amount to order book for future
        if order.remaining_amount > 0 and order.order_state in [Order.OrderState.WAITING, Order.OrderState.PARTIALLY_FILLED]:
            self._add_to_order_book(order)
        else:
            self._update_order_book(order)
        
        return {
            "status": "processed",
            "matched_amount": str(total_matched),
            "order_state": order.order_state
        }
    
    def _find_matching_orders(self, order: Order):
        """
        fine suitable order from opposite type of order (buy/sell) for matching
        """
        opposite_side = Order.OrderSide.SELL if order.order_side == Order.OrderSide.BUY else Order.OrderSide.BUY
        #order by price and creation time
        if opposite_side == Order.OrderSide.SELL:
            # for buy ,sell with lowest price
            order_by = ['price', 'created_at']
        else:
            # for sell ,buy with highest price
            order_by = ['-price', 'created_at']
        return Order.objects.filter(
            target_market=order.target_market,
            order_side=opposite_side,
            order_state__in=[Order.OrderState.WAITING, Order.OrderState.PARTIALLY_FILLED],
            remaining_amount__gt=0
        ).order_by(*order_by)
    
    def _price_matches_limit_order(self, order: Order, matching_order: Order) -> bool:
        """
        check order price for matching
        """
        if order.order_side == Order.OrderSide.BUY:
            #the buyer is willing to buy up to their own price.
            return matching_order.price <= order.price
        else:
            #the seller is willing to sell at least for his own price.
            return matching_order.price >= order.price
    
    def _create_trade(self, taker_order: Order, maker_order: Order, amount: Decimal):
       
        """
        create a trade between two orders
        """

        #trade price alwase is maker price (time priority)
        trade_price = maker_order.price
        
        trade = Trade.objects.create(
            maker=maker_order,
            taker=taker_order,
            price=trade_price,
            amount=amount,
            trade_market=taker_order.target_market,
            fee=taker_order.target_market.fee
        )
        
        return trade
    
    def _update_order_amounts(self, taker_order: Order, maker_order: Order, matched_amount: Decimal):
        """
        update maker and taker amount after matching
        """
        #update taker order
        taker_order.filled_amount = (taker_order.filled_amount or Decimal('0')) + matched_amount
        taker_order.remaining_amount = taker_order.amount - taker_order.filled_amount
        
        #update maker order
        maker_order.filled_amount = (maker_order.filled_amount or Decimal('0')) + matched_amount
        maker_order.remaining_amount = maker_order.amount - maker_order.filled_amount
        
        taker_order.save()
        maker_order.save()
        
        # update order state of maker order
        self._update_order_state(maker_order)
    
    def _update_order_state(self, order: Order):
        """
        update order state based on remaining price
        """
        if order.remaining_amount <= 0:
            order.order_state = Order.OrderState.FILLED
            order.filled_at = timezone.now()
        elif order.filled_amount > 0:
            order.order_state = Order.OrderState.PARTIALLY_FILLED
        
        order.save()
    
    def _add_to_order_book(self, order: Order):
        """
        append order to order book redis
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
            
            # create key for redis based on order date
            redis_key = f"orderbook:{market_symbol}:{side}"
            
            # add to sorted set with score equal to price
            if side == Order.OrderSide.BUY:
                # for buy highest price is priorit (- is for Descending order)
                score = float(-order.price)
            else:
                # for sell lowest price  is proprit
                score = float(order.price)
            
            self.redis_client.zadd(redis_key, {json.dumps(order_data): score})
            
            # update order book service
            order_book_service.update_order_book(market_symbol)
            
        except Exception as e:
            print(f"Error adding order {order.id} to order book: {str(e)}")
    
    def _update_order_book(self, order: Order):
        """
        update order book after  matching or canceling an order
        """
        try:
            market_symbol = order.target_market.symbol
            
            # remove order from order book redis after fill or cancel
            if order.order_state in [Order.OrderState.FILLED, Order.OrderState.CANCELED]:
                self._remove_from_order_book(order)
            
            # update orderbook service after change
            order_book_service.update_order_book(market_symbol)
            
        except Exception as e:
            print(f"Error updating order book for order {order.id}: {str(e)}")
    
    def _remove_from_order_book(self, order: Order):
        """
        remove order from order book cache
        """
        try:
            market_symbol = order.target_market.symbol
            side = order.order_side
            redis_key = f"orderbook:{market_symbol}:{side}"
            
            # find and remove order from sorted set
            all_orders = self.redis_client.zrange(redis_key, 0, -1)
            for order_json in all_orders:
                order_data = json.loads(order_json)
                if order_data['id'] == order.id:
                    self.redis_client.zrem(redis_key, order_json)
                    break
                    
        except Exception as e:
            print(f"Error removing order {order.id} from order book: {str(e)}")

engine = MatchingEngine() #using singleton pattern