from django.db import models
from core.models import BaseModel



class Currency(models.Model):
    # currency models for handle define new currency without edit code from django admin safely
    name =  models.CharField(max_length=50, unique=True)
    symbol = models.CharField(max_length=8, unique=True)

class Market(BaseModel):

    STATUS_CHOICES = [
        ('Active', 'active'),
        ('Suspend', 'suspend'),
        ('Deactive', 'deactive'),
    ]


    symbol = models.CharField(max_length=17, unique=True, editable=False)
    base_currency = models.ForeignKey('market.Currency',on_delete=models.DO_NOTHING, null=True,related_name ='market_base_currency')
    quote_currency = models.ForeignKey('market.Currency',on_delete=models.DO_NOTHING, null=True,related_name ='market_quote_currency')
    state = models.CharField(choices=STATUS_CHOICES, max_length=15, default='Active')
    fee = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    
    def __str__(self):
        return self.symbol
    
    class Meta:
        unique_together = ('first_currency','second_currency')
        indexes = [
            models.Index(fields=['base_currency','quote_currency']),
        ]

    def get_symbol(self):
        if not self.base_currency or not self.quote_currency:
            raise ValueError("Base and quote currency must be set")
        self.symbol = f"{self.base_currency.code}_{self.quote_currency.code}"
    
    def save(self, *args, **kwargs):
            self.symbol = self.get_symbol()
            super().save(*args, **kwargs)