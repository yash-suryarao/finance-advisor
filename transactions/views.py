from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import now
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from datetime import timedelta
from .models import Transaction, Budget, BudgetHistory, Category
from .nlp_processing import process_voice_transaction
from rest_framework import generics, filters, serializers
from rest_framework.pagination import PageNumberPagination
import csv
from .serializers import TransactionSerializer
import requests
from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import Profile
from .serializers import BudgetSerializer, BudgetHistorySerializer, CategorySerializer
import pytesseract
from PIL import Image
import re
import io

from .models import DeletedTransaction


# View for fetching latest 10 transactions
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transactions(request):
    transactions = Transaction.objects.filter(user=request.user).select_related('category').order_by('-date')[:10]  # Fetch latest 10 transactions

    data = [
        {
            "id": t.id,
            "category_name": t.category.name if t.category else "Other",  # Fetch category name
            "category_type": t.category_type,  # Income or Expense
            "description": t.description,
            "amount": float(t.amount),
            "date": t.date.isoformat(),  # Convert date to JSON format
        }
        for t in transactions
    ]
    
    return JsonResponse(data, safe=False)



# Pagination class for handling multiple transactions
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10  # Show 10 transactions per page
    page_size_query_param = 'page_size'
    max_page_size = 100


# View for listing and creating transactions
class TransactionListCreateView(generics.ListCreateAPIView):
    serializer_class = TransactionSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description']
    ordering_fields = ['date', 'amount']
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Transaction.objects.filter(user_id=user.id).order_by('-date')
        category = self.request.query_params.get('category', None)
        min_amount = self.request.query_params.get('min_amount', None)
        date = self.request.query_params.get('date', None)

        if category:
            queryset = queryset.filter(category__id=category)
        if min_amount:
            queryset = queryset.filter(amount__gte=min_amount)
        if date:
            queryset = queryset.filter(date=date)

        return queryset

    def perform_create(self, serializer):
        # Auto-categorize if description is provided but category is missing
        instance = serializer.validated_data
        if 'description' in instance and not instance.get('category'):
            try:
                from .categorizer import categorize_transaction
                predicted_cat_name = categorize_transaction(instance['description'])
                cat, _ = Category.objects.get_or_create(user=self.request.user, name=predicted_cat_name)
                serializer.save(user=self.request.user, category=cat)
                return
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to auto-categorize: {e}")
        serializer.save(user=self.request.user)



# View for fetching, updating and deleting a transaction
class TransactionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        DeletedTransaction.objects.create(
            user=instance.user,
            amount=instance.amount,
            category_name=instance.category.name if instance.category else None,
            category_type=instance.category_type,
            description=instance.description,
            date=instance.date
        )
        instance.delete()


# View for fetching all categories
class CategoryListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer

    def get_queryset(self):
        queryset = Category.objects.filter(user=self.request.user)
        if not queryset.exists():
            default_categories = ['Food', 'Transport', 'Shopping', 'Bills', 'Salary', 'Entertainment', 'Other']
            for name in default_categories:
                Category.objects.create(user=self.request.user, name=name)
            queryset = Category.objects.filter(user=self.request.user)
        return queryset



# View for fetching and creating budgets
class BudgetView(generics.ListCreateAPIView):
    serializer_class = BudgetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user)


class BudgetHistoryView(generics.ListAPIView):
    serializer_class = BudgetHistorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BudgetHistory.objects.filter(
            user=self.request.user, 
            month=self.request.query_params.get('month'), 
            year=self.request.query_params.get('year')
        )

