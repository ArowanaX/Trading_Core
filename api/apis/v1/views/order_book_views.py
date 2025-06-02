from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from orderbook.services import order_book_service
from ..serializers.orderbook_serializers import OrderBookSerializer

class OrderBookView(APIView):
    def get(self, request):
        serializer = OrderBookSerializer(data=request.query_params)
        if serializer.is_valid():
            order_book = order_book_service.get_order_book(
                market_symbol=serializer.validated_data['market_symbol'],
                limit=serializer.validated_data['limit']
            )
            return Response(order_book, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)