from django.contrib import admin
from .models import Order,Trade

@admin.register(Order)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('order_type', 'order_side','order_state','price','amount')
    list_filter = ('order_side','order_type','order_state')
    exclude =('filled_at',)

@admin.register(Trade)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('maker', 'taker','fee','amount','trade_market','created_at','filled_at')
    search_fields = ('maker','taker')
    
