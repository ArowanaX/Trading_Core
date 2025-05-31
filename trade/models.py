from django.db import models
from market.models import BaseModel
from django.core.validators import MinValueValidator


class Trade(BaseModel):   

    maker = models.ForeignKey('order.Order',on_delete=models.DO_NOTHING, related_name='maker_trades')
    taker = models.ForeignKey('order.Order',on_delete=models.DO_NOTHING, related_name='taker_trades')
    price = models.DecimalField(max_digits=40, decimal_places=16,validators=[MinValueValidator(0.000000000001)])
    amount = models.DecimalField(max_digits=32, decimal_places=8,validators=[MinValueValidator(0.000000000001)])

    
    def __str__(self):
        return f"{self.pk} : {self.maker.pk}/{self.taker.pk}"
    

    
