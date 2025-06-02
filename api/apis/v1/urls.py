
from django.urls import path
from api.apis.v1.views.market_views import MarketListCreateView
from api.apis.v1.views.orders_views import OrderCreateUpdateView
from api.apis.v1.views.order_book_views import OrderBookView

app_name = "api"

urlpatterns = [
    path("market/", MarketListCreateView.as_view(), name="market"),
    path("order/", OrderCreateUpdateView.as_view(), name="order"),
    path("order-book/", OrderBookView.as_view(), name="orderbook"),
]