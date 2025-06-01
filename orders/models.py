from django.db import models
from core.models import BaseModel
from django.core.validators import MinValueValidator
from decimal import Decimal


class Order(BaseModel):


    ORDER_TYPE=(('Market' , 'market'),('Limit','limit'))
    ORDER_SIDE=(('Buy','buy'),('Sell','sell'))
    ORDER_STATE=(('Waiting','waiting'),
                 ('Filled','filled'),
                 ('PartiallyFilled','partially_filled'),
                 ('PartiallyFilledAndFinished','partially_filled_and_finished'),
                 ('Canceled','canceled'),
                 ('Error','error'),
                 ('NotEnoughBalance','not_enough_balance'),
                 ('AutomaticallyCanceled','automatically_canceled'),
                 ('Idle','idle'))
        
       

    order_type = models.CharField(choices=ORDER_TYPE, max_length=15, default='Market', null=True,blank=True)
    order_side = models.CharField(choices=ORDER_SIDE, max_length=5)
    order_state = models.CharField(choices=ORDER_STATE, max_length=40)
    target_market = models.ForeignKey('currencies.Market',on_delete=models.DO_NOTHING, related_name='target_to_market')
    price = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)])
    amount = models.DecimalField(max_digits=32, decimal_places=8,validators=[MinValueValidator(0.000000000001)])
    filled_amount = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True, default=Decimal('0.0'))
    low_limit = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)],null=True,blank=True)
    high_limit = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)],null=True,blank=True)
    
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
    

    
