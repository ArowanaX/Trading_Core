from django.db import models
from core.models import BaseModel
from django.core.validators import MinValueValidator
from decimal import Decimal


class Order(BaseModel):


    class OrderType(models.TextChoices):
        MARKET = 'market', 'Market'
        LIMIT = 'limit', 'Limit'

    class OrderSide(models.TextChoices):
        BUY = 'buy', 'Buy'
        SELL = 'sell', 'Sell'

    class OrderState(models.TextChoices):
        WAITING = 'waiting', 'Waiting'
        FILLED = 'filled', 'Filled'
        PARTIALLY_FILLED = 'partially_filled', 'Partially Filled'
        PARTIALLY_FILLED_AND_FINISHED = 'partially_filled_and_finished', 'Partially Filled and Finished'
        CANCELED = 'canceled', 'Canceled'
        ERROR = 'error', 'Error'
        NOT_ENOUGH_BALANCE = 'not_enough_balance', 'Not Enough Balance'
        AUTOMATICALLY_CANCELED = 'automatically_canceled', 'Automatically Canceled'
        IDLE = 'idle', 'Idle'
       

    order_type = models.CharField(max_length=15, choices=OrderType.choices, default=OrderType.MARKET)
    order_side = models.CharField(max_length=5, choices=OrderSide.choices)
    order_state = models.CharField(max_length=40, choices=OrderState.choices, default=OrderState.WAITING)
    target_market = models.ForeignKey('currencies.Market',on_delete=models.DO_NOTHING, related_name='target_to_market')
    price = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)])
    amount = models.DecimalField(max_digits=32, decimal_places=8,validators=[MinValueValidator(0.000000000001)])
    filled_amount = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True, default=Decimal('0.0'))
    remaining_amount = models.DecimalField(max_digits=32, decimal_places=8, default=Decimal('0.0'))
    # low_limit = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)],null=True,blank=True)
    # high_limit = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)],null=True,blank=True)
    
    def __str__(self):
        return f"{self.pk} : {self.target_market.base_currency}/{self.target_market.quote_currency}"
    

    
class Trade(BaseModel):   

    maker = models.ForeignKey('orders.Order',on_delete=models.DO_NOTHING, related_name='maker_trades')
    taker = models.ForeignKey('orders.Order',on_delete=models.DO_NOTHING, related_name='taker_trades')
    price = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)])
    amount = models.DecimalField(max_digits=32, decimal_places=8,validators=[MinValueValidator(0.000000000001)])
    trade_market = models.ForeignKey('currencies.Market',on_delete=models.DO_NOTHING, related_name='trade_to_market')
    fee = models.DecimalField(max_digits=5, decimal_places=4, default=0)


    
    def __str__(self):
        return f"{self.pk} : {self.maker.pk}/{self.taker.pk}"
    

    
