from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from ..serializers.orders_serializers import OrderCreateSerializer , CancelOrderSerializer
from django.db import transaction
from orders.services import engine


class OrderCreateUpdateView(APIView):
    # Create a new order and change order state to cancel

    def post(self, request):
            serializer = OrderCreateSerializer(data=request.data)
            if serializer.is_valid():
                with transaction.atomic():
                    order = serializer.save()
                    engine.process_order(order.id) 
                    return Response({"order_id": order.id, "status": "created"}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        print(request.data)
        serializer = CancelOrderSerializer(data=request.data)
        if serializer.is_valid():
            with transaction.atomic():
                order = serializer.validated_data['order_id']
                order.order_state = 'canceled'
                order.save()
                engine._update_order_book(order)
                return Response({"order_id": order.id, "status": "canceled"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)