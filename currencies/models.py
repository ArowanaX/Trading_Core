from django.db import models
from core.models import BaseModel
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal

class Currency(models.Model):
    # currency models for handle define new currency without edit code from django admin safely
    name =  models.CharField(max_length=50, unique=True)
    symbol = models.CharField(max_length=8, unique=True)

    def __str__(self):
        return self.symbol

class Market(BaseModel):

    STATUS_CHOICES = [
        ('Active', 'active'),
        ('Suspend', 'suspend'),
        ('Deactive', 'deactive'),
    ]


    symbol = models.CharField(max_length=17, unique=True, editable=False)
    base_currency = models.ForeignKey('currencies.Currency',on_delete=models.DO_NOTHING, null=True,related_name ='market_base_currency')
    quote_currency = models.ForeignKey('currencies.Currency',on_delete=models.DO_NOTHING, null=True,related_name ='market_quote_currency')
    state = models.CharField(choices=STATUS_CHOICES, max_length=15, default='Active')
    fee = models.DecimalField(max_digits=10, decimal_places=9, default=0, validators=[MinValueValidator(Decimal('0.000000001'))])
    
    def __str__(self):
        return self.symbol
    
    class Meta:
        unique_together = ('base_currency','quote_currency')
        indexes = [
            models.Index(fields=['base_currency','quote_currency']),
        ]

    def get_symbol(self):
        if not self.base_currency or not self.quote_currency:
            raise ValueError("Base and quote currency must be set")
        return f"{self.base_currency.symbol}_{self.quote_currency.symbol}"
    
    def save(self, *args, **kwargs):
            self.symbol = self.get_symbol()
            if self.base_currency == self.quote_currency:
                raise ValidationError("Cant create market with same base and quote currency.!")
            super().save(*args, **kwargs)