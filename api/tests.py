import pytest
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from rest_framework.test import APITestCase
from rest_framework import status
from currencies.models import Currency, Market
from orders.models import Order, Trade
from orders.services import engine
from orderbook.services import order_book_service
import redis
import json
from django.utils import timezone
from django.db.models import Sum
from unittest.mock import patch, MagicMock

class CurrencyMarketTests(TestCase):
    #test cases for currency and market models
    
    def setUp(self):
        #set up test currencys
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        self.eth = Currency.objects.create(name="Ethereum", symbol="ETH")
    
    def test_create_market_success_200(self):
        #test succesful market creation with 200 scenario
        market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
        
        self.assertEqual(market.symbol, "BTC_USDT")
        self.assertEqual(market.base_currency, self.btc)
        self.assertEqual(market.quote_currency, self.usdt)
        self.assertEqual(market.fee, Decimal('0.001'))
        self.assertEqual(market.state, 'Active')
    
    def test_create_market_same_base_quote_currency(self):
        #test market creation with same base and quote currency shoud fail
        with self.assertRaises(ValidationError):
            market = Market.objects.create(
                base_currency=self.btc,
                quote_currency=self.btc,
                fee=Decimal('0.001')
            )
            market.full_clean()
    
    def test_create_market_duplicate_symbol(self):
        #test market creation with duplicat symbol should fail
        Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
        
        with self.assertRaises(IntegrityError):
            Market.objects.create(
                base_currency=self.btc,
                quote_currency=self.usdt,
                fee=Decimal('0.002')
            )

class OrderCreationTests(TestCase):
    #test cases for order creation scenarios
    
    def setUp(self):
        #set up test data for order tests
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        self.market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
    
    def test_create_market_order_buy_success_200(self):
        #test succesful market buy order creation
        order = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.1')
        )
        
        self.assertEqual(order.order_type, Order.OrderType.MARKET)
        self.assertEqual(order.order_side, Order.OrderSide.BUY)
        self.assertEqual(order.order_state, Order.OrderState.WAITING)
        self.assertEqual(order.remaining_amount, Decimal('0.0'))
    
    def test_create_limit_order_sell_success_200(self):
        #test succesful limit sell order creation
        order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('51000.00'),
            amount=Decimal('0.2')
        )
        
        self.assertEqual(order.order_type, Order.OrderType.LIMIT)
        self.assertEqual(order.order_side, Order.OrderSide.SELL)
        self.assertEqual(order.price, Decimal('51000.00'))
    
    def test_create_order_without_target_market(self):
        #test order creation without target market shoud fail
        with self.assertRaises(IntegrityError):
            Order.objects.create(
                order_type=Order.OrderType.MARKET,
                order_side=Order.OrderSide.BUY,
                price=Decimal('50000.00'),
                amount=Decimal('0.1')
            )
    
    def test_create_order_negative_price(self):
        #test order creation with negative price shoud fail
        with self.assertRaises(ValidationError):
            order = Order(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('-1000.00'),
                amount=Decimal('0.1')
            )
            order.full_clean()
    
    def test_create_order_zero_price(self):
        #test order creation with zero price shoud fail
        with self.assertRaises(ValidationError):
            order = Order(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('0.00'),
                amount=Decimal('0.1')
            )
            order.full_clean()
    
    def test_create_order_negative_amount(self):
        #test order creation with negative amount shoud fail
        with self.assertRaises(ValidationError):
            order = Order(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('50000.00'),
                amount=Decimal('-0.1')
            )
            order.full_clean()
    
    def test_create_order_zero_amount(self):
        #test order creation with zero amount shoud fail
        with self.assertRaises(ValidationError):
            order = Order(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('50000.00'),
                amount=Decimal('0.00')
            )
            order.full_clean()

class OrderMatchingTests(TestCase):
    #test cases for order matching engine
    
    def setUp(self):
        #set up test data for matching tests
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        self.market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
        
        #clear Redis before each test
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        redis_client.flushdb()
    
    def test_create_multiple_orders_for_order_book(self):
        #test creating multiple orders to build order book
        sell_order_1 = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('51000.00'),
            amount=Decimal('0.1')
        )
        
        sell_order_2 = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('52000.00'),
            amount=Decimal('0.2')
        )
        
        buy_order_1 = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('49000.00'),
            amount=Decimal('0.15')
        )
        
        buy_order_2 = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('48000.00'),
            amount=Decimal('0.25')
        )
        
        engine.process_order(sell_order_1.id)
        engine.process_order(sell_order_2.id)
        engine.process_order(buy_order_1.id)
        engine.process_order(buy_order_2.id)
        
        sell_order_1.refresh_from_db()
        sell_order_2.refresh_from_db()
        buy_order_1.refresh_from_db()
        buy_order_2.refresh_from_db()
        
        self.assertEqual(sell_order_1.order_state, Order.OrderState.WAITING)
        self.assertEqual(buy_order_1.order_state, Order.OrderState.WAITING)
    
    def test_orders_matching_from_order_book(self):
        #test orders matching from order book
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.2')
        )
        engine.process_order(sell_order.id)
        
        buy_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50500.00'),
            amount=Decimal('0.1')
        )
        engine.process_order(buy_order.id)
        
        sell_order.refresh_from_db()
        buy_order.refresh_from_db()
        
        self.assertEqual(buy_order.order_state, Order.OrderState.FILLED)
        self.assertEqual(buy_order.filled_amount, Decimal('0.1'))
        
        self.assertEqual(sell_order.order_state, Order.OrderState.PARTIALLY_FILLED)
        self.assertEqual(sell_order.filled_amount, Decimal('0.1'))
        self.assertEqual(sell_order.remaining_amount, Decimal('0.1'))
        
        trade = Trade.objects.filter(maker=sell_order, taker=buy_order).first()
        self.assertIsNotNone(trade)
        self.assertEqual(trade.price, Decimal('50000.00'))
        self.assertEqual(trade.amount, Decimal('0.1'))
    
    def test_partial_fill_order(self):
        #test partial fill senario
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('1.0')
        )
        engine.process_order(sell_order.id)
        
        buy_order = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.3')
        )
        engine.process_order(buy_order.id)
        
        sell_order.refresh_from_db()
        buy_order.refresh_from_db()
        
        self.assertEqual(sell_order.order_state, Order.OrderState.PARTIALLY_FILLED)
        self.assertEqual(sell_order.filled_amount, Decimal('0.3'))
        self.assertEqual(sell_order.remaining_amount, Decimal('0.7'))
        
        self.assertEqual(buy_order.order_state, Order.OrderState.FILLED)
        self.assertEqual(buy_order.filled_amount, Decimal('0.3'))
    
    def test_complete_partial_filled_order(self):
        #test completing a partially filled order
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.5')
        )
        engine.process_order(sell_order.id)
        
        buy_order_1 = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.2')
        )
        engine.process_order(buy_order_1.id)
        
        sell_order.refresh_from_db()
        self.assertEqual(sell_order.order_state, Order.OrderState.PARTIALLY_FILLED)
        
        buy_order_2 = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.3')
        )
        engine.process_order(buy_order_2.id)
        
        sell_order.refresh_from_db()
        buy_order_2.refresh_from_db()
        
        self.assertEqual(sell_order.order_state, Order.OrderState.FILLED)
        self.assertEqual(sell_order.filled_amount, Decimal('0.5'))
        self.assertEqual(sell_order.remaining_amount, Decimal('0.0'))
        
        self.assertEqual(buy_order_2.order_state, Order.OrderState.FILLED)
        
        trades = Trade.objects.filter(maker=sell_order)
        self.assertEqual(trades.count(), 2)

class OrderCancellationTests(TestCase):
    #test cases for order cancelation
    
    def setUp(self):
        #set up test data for cancelation tests
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        self.market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
    
    def test_cancel_waiting_order(self):
        #test canceling an order in waiting state
        order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('49000.00'),
            amount=Decimal('0.1')
        )
        
        order.order_state = Order.OrderState.CANCELED
        order.save()
        
        self.assertEqual(order.order_state, Order.OrderState.CANCELED)
    
    def test_cancel_partially_filled_order(self):
        #test canceling a partialy filled order
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('1.0')
        )
        engine.process_order(sell_order.id)
        
        buy_order = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.3')
        )
        engine.process_order(buy_order.id)
        
        sell_order.refresh_from_db()
        self.assertEqual(sell_order.order_state, Order.OrderState.PARTIALLY_FILLED)
        
        sell_order.order_state = Order.OrderState.CANCELED
        sell_order.save()
        
        engine._update_order_book(sell_order)
        
        self.assertEqual(sell_order.order_state, Order.OrderState.CANCELED)
        self.assertEqual(sell_order.filled_amount, Decimal('0.3'))
        self.assertEqual(sell_order.remaining_amount, Decimal('0.7'))

class OrderBookTests(TestCase):
    #test cases for order book functionality
    
    def setUp(self):
        #set up test data for order book tests
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        self.market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
        
        #clear Redis before each test
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        redis_client.flushdb()
    
    def test_order_book_empty_market(self):
        #test order book for empty market
        order_book = order_book_service.get_order_book(self.market.symbol)
        
        self.assertEqual(order_book['market_symbol'], self.market.symbol)
        self.assertEqual(len(order_book['buy']), 0)
        self.assertEqual(len(order_book['sell']), 0)
    
    def test_order_book_with_orders(self):
        #test order book with some orders
        sell_orders = [
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.SELL,
                target_market=self.market,
                price=Decimal('51000.00'),
                amount=Decimal('0.1')
            ),
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.SELL,
                target_market=self.market,
                price=Decimal('52000.00'),
                amount=Decimal('0.2')
            ),
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.SELL,
                target_market=self.market,
                price=Decimal('50500.00'),
                amount=Decimal('0.15')
            )
        ]
        
        buy_orders = [
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('49000.00'),
                amount=Decimal('0.1')
            ),
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('48000.00'),
                amount=Decimal('0.2')
            ),
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('49500.00'),
                amount=Decimal('0.15')
            )
        ]
        
        for order in sell_orders + buy_orders:
            engine.process_order(order.id)
        
        order_book = order_book_service.get_order_book(self.market.symbol)
        
        sell_prices = [item['price'] for item in order_book['sell']]
        self.assertEqual(sell_prices, sorted(sell_prices))
        self.assertEqual(sell_prices[0], 50500.0)
        
        buy_prices = [item['price'] for item in order_book['buy']]
        self.assertEqual(buy_prices, sorted(buy_prices, reverse=True))
        self.assertEqual(buy_prices[0], 49500.0)
    
    def test_order_book_sync_functionality(self):
        #test order book synchronisation between Redis and postgres
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('51000.00'),
            amount=Decimal('0.1')
        )
        engine.process_order(sell_order.id)
        
        redis_client = redis.Redis(host='localhost', port=6379, db=0)
        redis_client.flushdb()
        
        order_book = order_book_service.get_order_book(self.market.symbol)
        
        self.assertEqual(len(order_book['sell']), 1)
        self.assertEqual(order_book['sell'][0]['price'], 51000.0)
        self.assertEqual(order_book['sell'][0]['amount'], 0.1)

class FinancialIntegrityTests(TestCase):
    #test cases for financial integrity and calulations
    
    def setUp(self):
        #set up test data for financial tests
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        self.market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
    
    def test_trade_amount_calculation_integrity(self):
        #test that trade amounts are calculated corectly
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.5')
        )
        engine.process_order(sell_order.id)
        
        buy_order = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('0.3')
        )
        engine.process_order(buy_order.id)
        
        sell_order.refresh_from_db()
        buy_order.refresh_from_db()
        
        self.assertEqual(sell_order.filled_amount, buy_order.filled_amount)
        self.assertEqual(sell_order.amount, sell_order.filled_amount + sell_order.remaining_amount)
        self.assertEqual(buy_order.amount, buy_order.filled_amount + buy_order.remaining_amount)
        
        trade = Trade.objects.filter(maker=sell_order, taker=buy_order).first()
        self.assertEqual(trade.amount, buy_order.filled_amount)
        self.assertEqual(trade.amount, sell_order.filled_amount)
    
    def test_multiple_trades_financial_integrity(self):
        #test financial integrity across multiple trades
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('1.0')
        )
        engine.process_order(sell_order.id)
        
        buy_amounts = [Decimal('0.2'), Decimal('0.3'), Decimal('0.4')]
        total_buy_amount = sum(buy_amounts)
        
        for amount in buy_amounts:
            buy_order = Order.objects.create(
                order_type=Order.OrderType.MARKET,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('50000.00'),
                amount=amount
            )
            engine.process_order(buy_order.id)
        
        sell_order.refresh_from_db()
        self.assertEqual(sell_order.filled_amount, total_buy_amount)
        self.assertEqual(sell_order.remaining_amount, sell_order.amount - total_buy_amount)
        
        trades = Trade.objects.filter(maker=sell_order)
        total_trade_amount = sum(trade.amount for trade in trades)
        self.assertEqual(total_trade_amount, total_buy_amount)

class SingletonPatternTests(TestCase):
    #test cases for singleton pattern 
    
    def test_matching_engine_singleton_pattern(self):
        #test that matching engine follows singleton pattern
        from orders.services import engine as engine1
        from orders.services import engine as engine2
        
        self.assertIs(engine1, engine2)
        self.assertIs(engine1.redis_client, engine2.redis_client)
    
    def test_order_book_service_singleton_pattern(self):
        #test that order book service follows singleton pattern
        from orderbook.services import order_book_service as service1
        from orderbook.services import order_book_service as service2
        
        self.assertIs(service1, service2)
        self.assertIs(service1.redis_client, service2.redis_client)

class APIIntegrationTests(APITestCase):
    #integration tests for API endpoints
    
    def setUp(self):
        #set up test data for API tests
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        self.market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
    
    def test_create_order_api_success(self):
        #test order creation through API
        url = '/order/'
        data = {
            'target_market': 'BTC_USDT',
            'order_type': 'limit',
            'order_side': 'buy',
            'price': '49000.00',
            'amount': '0.1'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('order_id', response.data)
        
        order = Order.objects.get(id=response.data['order_id'])
        self.assertEqual(order.target_market, self.market)
        self.assertEqual(order.price, Decimal('49000.00'))
    
    def test_get_order_book_api(self):
        #test order book retrival through API
        Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('51000.00'),
            amount=Decimal('0.1')
        )
        
        url = '/order-book/'
        params = {'market_symbol': 'BTC_USDT', 'limit': 10}
        
        response = self.client.get(url, params)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('market_symbol', response.data)
        self.assertIn('buy', response.data)
        self.assertIn('sell', response.data)
    
    def test_cancel_order_api(self):
        #test order cancelation through API
        order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('49000.00'),
            amount=Decimal('0.1')
        )
        
        url = '/order/'
        data = {'order_id': str(order.id)}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'canceled')
        
        order.refresh_from_db()
        self.assertEqual(order.order_state, Order.OrderState.CANCELED)

class TestTradingEngineIntegration(TransactionTestCase):
    #completed integration tests for the trading engine system

    def setUp(self):
        #set up test data and Redis mock
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        
        self.market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.002')
        )
        
        self.redis_mock = MagicMock()
        self.redis_patcher = patch('orders.services.redis.Redis')
        self.mock_redis_class = self.redis_patcher.start()
        self.mock_redis_class.return_value = self.redis_mock
        
        self.orderbook_redis_patcher = patch('orderbook.services.redis.Redis')
        self.mock_orderbook_redis_class = self.orderbook_redis_patcher.start()
        self.mock_orderbook_redis_class.return_value = self.redis_mock
        
        self.engine = engine
        self.orderbook_service = order_book_service

    def tearDown(self):
        #clean up patches
        self.redis_patcher.stop()
        self.orderbook_redis_patcher.stop()

    def test_cancel_partially_filled_order(self):
        #test canceling a partialy filled order and verify financial consistency
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('10.0'),
            remaining_amount=Decimal('10.0')
        )
        
        buy_order = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('3.0'),
            remaining_amount=Decimal('3.0')
        )
        
        result = self.engine.process_order(buy_order.id)
        
        sell_order.refresh_from_db()
        buy_order.refresh_from_db()
        
        assert result["status"] == "processed"
        assert buy_order.order_state == Order.OrderState.FILLED
        assert sell_order.order_state == Order.OrderState.PARTIALLY_FILLED
        assert sell_order.filled_amount == Decimal('3.0')
        assert sell_order.remaining_amount == Decimal('7.0')
        
        trade = Trade.objects.get(maker=sell_order, taker=buy_order)
        assert trade.amount == Decimal('3.0')
        assert trade.price == Decimal('50000.00')
        
        original_filled_amount = sell_order.filled_amount
        sell_order.order_state = Order.OrderState.CANCELED
        sell_order.save()
        
        sell_order.refresh_from_db()
        assert sell_order.order_state == Order.OrderState.CANCELED
        assert sell_order.filled_amount == original_filled_amount
        
        trade.refresh_from_db()
        assert trade.amount == Decimal('3.0')
        assert Trade.objects.filter(maker=sell_order).count() == 1

    def test_order_book_different_scenarios(self):
        #test order book functionality in varius market scenarios
        result = self.orderbook_service.get_order_book(self.market.symbol)
        assert result["market_symbol"] == self.market.symbol
        assert result["sell"] == []
        assert result["buy"] == []
        
        buy_orders = [
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('49000.00'),
                amount=Decimal('2.0'),
                remaining_amount=Decimal('2.0')
            ),
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('48000.00'),
                amount=Decimal('3.0'),
                remaining_amount=Decimal('3.0')
            ),
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('49000.00'),
                amount=Decimal('1.5'),
                remaining_amount=Decimal('1.5')
            )
        ]
        
        sell_orders = [
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.SELL,
                target_market=self.market,
                price=Decimal('51000.00'),
                amount=Decimal('1.0'),
                remaining_amount=Decimal('1.0')
            ),
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.SELL,
                target_market=self.market,
                price=Decimal('52000.00'),
                amount=Decimal('2.5'),
                remaining_amount=Decimal('2.5')
            )
        ]
        
        def mock_zrange_side_effect(key, start, end, withscores=True):
            if 'buy' in key:
                return [
                    (json.dumps({'id': buy_orders[0].id, 'price': '49000.00', 'amount': '2.0', 'created_at': '2025-01-01T00:00:00'}), -49000.0),
                    (json.dumps({'id': buy_orders[2].id, 'price': '49000.00', 'amount': '1.5', 'created_at': '2025-01-01T00:01:00'}), -49000.0),
                    (json.dumps({'id': buy_orders[1].id, 'price': '48000.00', 'amount': '3.0', 'created_at': '2025-01-01T00:02:00'}), -48000.0)
                ]
            elif 'sell' in key:
                return [
                    (json.dumps({'id': sell_orders[0].id, 'price': '51000.00', 'amount': '1.0', 'created_at': '2025-01-01T00:00:00'}), 51000.0),
                    (json.dumps({'id': sell_orders[1].id, 'price': '52000.00', 'amount': '2.5', 'created_at': '2025-01-01T00:01:00'}), 52000.0)
                ]
            return []
        
        self.redis_mock.zrange.side_effect = mock_zrange_side_effect
        
        result = self.orderbook_service.get_order_book(self.market.symbol, limit=10)
        
        assert len(result["sell"]) == 2
        assert result["sell"][0]["price"] == 51000.0
        assert result["sell"][1]["price"] == 52000.0
        
        assert len(result["buy"]) == 2
        assert result["buy"][0]["price"] == 49000.0
        assert result["buy"][0]["amount"] == 3.5
        assert result["buy"][1]["price"] == 48000.0
        assert result["buy"][1]["amount"] == 3.0

    def test_core_functionality_correctness(self):
        #test the corectness of core trading engine functionality
        limit_sell = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('5.0'),
            remaining_amount=Decimal('5.0')
        )
        
        market_buy = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('52000.00'),
            amount=Decimal('2.0'),
            remaining_amount=Decimal('2.0')
        )
        
        result = self.engine.process_order(market_buy.id)
        
        assert result["status"] == "processed"
        assert Decimal(result["matched_amount"]) == Decimal('2.0')
        
        limit_sell.refresh_from_db()
        market_buy.refresh_from_db()
        
        assert market_buy.order_state == Order.OrderState.FILLED
        assert limit_sell.order_state == Order.OrderState.PARTIALLY_FILLED
        assert limit_sell.remaining_amount == Decimal('3.0')
        
        trade = Trade.objects.get(maker=limit_sell, taker=market_buy)
        assert trade.price == Decimal('50000.00')
        assert trade.amount == Decimal('2.0')
        
        high_price_buy = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('49000.00'),
            amount=Decimal('1.0'),
            remaining_amount=Decimal('1.0')
        )
        
        result = self.engine.process_order(high_price_buy.id)
        
        high_price_buy.refresh_from_db()
        limit_sell.refresh_from_db()
        
        assert high_price_buy.order_state == Order.OrderState.WAITING
        assert limit_sell.remaining_amount == Decimal('3.0')
        
        sell_order_1 = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('51000.00'),
            amount=Decimal('2.0'),
            remaining_amount=Decimal('2.0'),
            created_at=timezone.now()
        )
        
        import time
        time.sleep(0.1)
        
        sell_order_2 = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('51000.00'),
            amount=Decimal('1.5'),
            remaining_amount=Decimal('1.5'),
            created_at=timezone.now()
        )
        
        large_buy = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('52000.00'),
            amount=Decimal('3.0'),
            remaining_amount=Decimal('3.0')
        )
        
        self.engine.process_order(sell_order_1.id)
        self.engine.process_order(sell_order_2.id)
        self.engine.process_order(large_buy.id)
        
        sell_order_1.refresh_from_db()
        sell_order_2.refresh_from_db()
        large_buy.refresh_from_db()
        
        assert sell_order_1.order_state == Order.OrderState.FILLED
        assert sell_order_2.order_state == Order.OrderState.PARTIALLY_FILLED
        assert sell_order_2.remaining_amount == Decimal('0.5')
        assert large_buy.order_state == Order.OrderState.FILLED

    def test_financial_calculations_and_consistency(self):
        #test financial calulations accuracy and prevent financial discrepancys
        sell_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('33333.333333'),
            amount=Decimal('1.23456789'),
            remaining_amount=Decimal('1.23456789')
        )
        
        buy_order = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('35000.00'),
            amount=Decimal('0.5'),
            remaining_amount=Decimal('0.5')
        )
        
        result = self.engine.process_order(buy_order.id)
        
        sell_order.refresh_from_db()
        buy_order.refresh_from_db()
        
        expected_remaining = Decimal('1.23456789') - Decimal('0.5')
        assert sell_order.remaining_amount == expected_remaining
        assert sell_order.filled_amount == Decimal('0.5')
        assert buy_order.filled_amount == Decimal('0.5')
        
        Trade.objects.all().delete()
        Order.objects.all().delete()
        
        initial_sell_amount = Decimal('10.0')
        
        large_sell = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('45000.00'),
            amount=initial_sell_amount,
            remaining_amount=initial_sell_amount
        )
        
        buy_amounts = [Decimal('2.5'), Decimal('1.8'), Decimal('3.2'), Decimal('2.5')]
        total_buy_amount = sum(buy_amounts)
        
        trades_before = Trade.objects.count()
        
        for amount in buy_amounts:
            large_sell.refresh_from_db()
            buy_order = Order.objects.create(
                order_type=Order.OrderType.MARKET,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('46000.00'),
                amount=amount,
                remaining_amount=amount
            )
            self.engine.process_order(buy_order.id)
        
        large_sell.refresh_from_db()
        
        assert large_sell.filled_amount == total_buy_amount
        assert large_sell.remaining_amount == initial_sell_amount - total_buy_amount
        
        trades_after = Trade.objects.count()
        assert trades_after - trades_before == len(buy_amounts)
        
        total_trade_amount = Trade.objects.filter(
            maker=large_sell
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        assert total_trade_amount == total_buy_amount
        
        trade = Trade.objects.filter(maker=large_sell).first()
        assert trade.fee == self.market.fee
        
        with pytest.raises(Exception):
            invalid_order = Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('-100.00'),
                amount=Decimal('1.0'),
                remaining_amount=Decimal('1.0')
            )
            invalid_order.full_clean()

    def test_order_book_redis_synchronization(self):
        #test synchronisation between Redis and database for order book
        orders = [
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('48000.00'),
                amount=Decimal('2.0'),
                remaining_amount=Decimal('2.0')
            ),
            Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.SELL,
                target_market=self.market,
                price=Decimal('52000.00'),
                amount=Decimal('1.5'),
                remaining_amount=Decimal('1.5')
            )
        ]
        
        self.orderbook_service.redis_client = self.redis_mock
        self.orderbook_service.sync_order_book(self.market.symbol)
        
        assert self.redis_mock.set.called
        assert self.redis_mock.delete.called
        assert self.redis_mock.zadd.called
        
        self.redis_mock.zcard.return_value = 5
        self.redis_mock.get.return_value = "2025-01-01T12:00:00"
        
        stats = self.orderbook_service.get_order_book_stats(self.market.symbol)
        
        assert stats["market_symbol"] == self.market.symbol
        assert stats["buy_orders_count"] == 5
        assert stats["sell_orders_count"] == 5
        assert stats["total_orders"] == 10

    def test_error_handling_and_edge_cases(self):
        #test error handling and edge cases
        result = self.engine.process_order(99999)
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()
        
        processed_order = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('1.0'),
            remaining_amount=Decimal('0.0'),
            order_state=Order.OrderState.FILLED
        )
        
        result = self.engine.process_order(processed_order.id)
        assert result["status"] == "error"
        assert "not in waiting state" in result["message"].lower()
        
        isolated_order = Order.objects.create(
            order_type=Order.OrderType.MARKET,
            order_side=Order.OrderSide.BUY,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('1.0'),
            remaining_amount=Decimal('1.0')
        )
        
        result = self.engine.process_order(isolated_order.id)
        assert result["status"] == "no_match"
        
        isolated_order.refresh_from_db()
        assert isolated_order.order_state == Order.OrderState.ERROR
        
        result = self.orderbook_service.get_order_book("INVALID_MARKET")
        assert "error" in result or result["sell"] == []

    def test_concurrent_order_processing(self):
        #test concurrent order processing senarios
        target_sell = Order.objects.create(
            order_type=Order.OrderType.LIMIT,
            order_side=Order.OrderSide.SELL,
            target_market=self.market,
            price=Decimal('50000.00'),
            amount=Decimal('5.0'),
            remaining_amount=Decimal('5.0')
        )
        
        buy_orders = []
        for i in range(3):
            buy_order = Order.objects.create(
                order_type=Order.OrderType.MARKET,
                order_side=Order.OrderSide.BUY,
                target_market=self.market,
                price=Decimal('51000.00'),
                amount=Decimal('2.0'),
                remaining_amount=Decimal('2.0')
            )
            buy_orders.append(buy_order)
        
        results = []
        for buy_order in buy_orders:
            result = self.engine.process_order(buy_order.id)
            results.append(result)
        
        target_sell.refresh_from_db()
        
        for bo in buy_orders:
            bo.refresh_from_db()
        
        total_filled_amount = sum(bo.filled_amount or Decimal('0') for bo in buy_orders)
        assert total_filled_amount == Decimal('5.0')
        assert target_sell.order_state == Order.OrderState.FILLED

def create_test_market_data():
    #utility function to create realistic test market data
    btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
    eth = Currency.objects.create(name="Ethereum", symbol="ETH")
    usdt = Currency.objects.create(name="Tether", symbol="USDT")
    
    markets = [
        Market.objects.create(base_currency=btc, quote_currency=usdt, fee=Decimal('0.001')),
        Market.objects.create(base_currency=eth, quote_currency=usdt, fee=Decimal('0.0015')),
        Market.objects.create(base_currency=btc, quote_currency=eth, fee=Decimal('0.002'))
    ]
    
    return markets

@pytest.mark.performance
class TestTradingEnginePerformance(TransactionTestCase):
    #performance tests for the trading engine
    
    def setUp(self):
        self.btc = Currency.objects.create(name="Bitcoin", symbol="BTC")
        self.usdt = Currency.objects.create(name="Tether", symbol="USDT")
        self.market = Market.objects.create(
            base_currency=self.btc,
            quote_currency=self.usdt,
            fee=Decimal('0.001')
        )
        self.engine = engine
    
    def test_high_volume_order_processing(self):
        #test processing of high volume of orders
        import time
        
        num_orders = 100
        start_time = time.time()
        
        for i in range(num_orders):
            order = Order.objects.create(
                order_type=Order.OrderType.LIMIT,
                order_side=Order.OrderSide.BUY if i % 2 == 0 else Order.OrderSide.SELL,
                target_market=self.market,
                price=Decimal('50000.00') + Decimal(str(i)),
                amount=Decimal('1.0'),
                remaining_amount=Decimal('1.0')
            )
            
            if i % 4 == 0:
                self.engine.process_order(order.id)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert processing_time < 1, f"Processing took too long: {processing_time} seconds"
        print(f"Processing time is {processing_time} sec for {num_orders} orders")
        assert Trade.objects.count() > 0