from django.contrib import admin
from .models import Currency,Market

@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'name')
    search_fields = ('symbol','name')


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'base_currency','quote_currency','state','created_at')
    search_fields = ('base_currency','quote_currency')
    list_filter = ('state','base_currency','quote_currency')
    fields = ('base_currency','quote_currency','state','fee')
