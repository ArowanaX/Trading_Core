from .models import Currency,Market


class MarketService:
    @staticmethod
    def create_market(base_currency_code, quote_currency_code, state='active'):
        base_currency = Currency.objects.get(code=base_currency_code)
        quote_currency = Currency.objects.get(code=quote_currency_code)
        symbol = f"{base_currency.code}_{quote_currency.code}"
        market, created = Market.objects.get_or_create(
            base_currency=base_currency,
            quote_currency=quote_currency,
            defaults={'symbol': symbol, 'state': state}
        )
        return market