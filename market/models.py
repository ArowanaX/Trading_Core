from django.db import models


class BaseModel(models.Model):
    # Abstract model for created_at and updated_at  and filled at fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    filled_at = models.DateField(null=True,blank=True)

    class Meta:
        abstract = True

class Currency(models.model):
    # currency models for handle define new currency without edit code from django admin safely
    name =  models.CharField(max_length=8, unique=True)
    simbol = models.CharField(max_length=8, unique=True)

class Market(BaseModel):
    ACTIVE = 'active'
    SUSPEND = 'suspend'
    DEACTIVE = 'deactive'

    STATUS_CHOICES = [
        (ACTIVE, 'active'),
        (SUSPEND, 'suspend'),
        (DEACTIVE, 'deactive'),
    ]


    simbol = models.CharField(max_length=17, null=True, db_index=True, unique=True)
    first_currency = models.ForeignKey('Currency',on_delete=models.DO_NOTHING, null=True)
    second_currency = models.ForeignKey('Currency',on_delete=models.DO_NOTHING, null=True)
    state = models.CharField(choices=STATUS_CHOICES, max_length=15, default=ACTIVE)
    
    def __str__(self):
        return self.simbol
    
    class Meta:
        unique_together = ('first_currency','second_currency')
    
