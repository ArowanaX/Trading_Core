from django.db import models
from market.models import BaseModel, Market
from django.core.validators import MinValueValidator
from decimal import Decimal


class Order(BaseModel):

    @staticmethod
    def get_market_symbols():
        # Fetch all market symbols from the Market model
        try:
            return [(market.symbol, market.symbol) for market in Market.objects.all()]
        except:
            return None
    

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
        
       

    first_currency = models.ForeignKey('market.Currency',on_delete=models.DO_NOTHING, related_name='orders_as_first')
    second_currency = models.ForeignKey('market.Currency',on_delete=models.DO_NOTHING, related_name='orders_as_second')
    order_type = models.CharField(choices=ORDER_TYPE, max_length=15, default='Market', null=True,blank=True)
    order_side = models.CharField(choices=ORDER_SIDE, max_length=5)
    order_state = models.CharField(choices=ORDER_STATE, max_length=40)
    target_market = models.CharField(max_length=10, choices=get_market_symbols())
    price = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)])
    amount = models.DecimalField(max_digits=32, decimal_places=8,validators=[MinValueValidator(0.000000000001)])
    filled_amount = models.DecimalField(max_digits=24, decimal_places=8, null=True, blank=True, default=Decimal('0.0'))
    low_limit = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)])
    high_limit = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)])
    
    def __str__(self):
        return f"{self.pk} : {self.first_currency}/{self.second_currency}"
    

    
