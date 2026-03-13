"""
TRANSACTIONS MODULE - VIEWS (transactions/views.py)
---------------------------------------------------
This file handles the core financial data entry and retrieval for the user.
It is organized into four main sections:
1. CORE TRANSACTIONS MODULE: Endpoints to create, read, update, and delete transactions.
2. CATEGORIES MODULE: Endpoints to list and auto-provision standard spending categories.
3. BUDGETING MODULE: Endpoints to set monthly limits and track historical budgets.
4. AI & AUTOMATIONS MODULE: Endpoints linking to the ML categorization models.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils.timezone import now
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from datetime import timedelta
from .models import Transaction, Budget, BudgetHistory, Category
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

# ==========================================
# 1. CORE TRANSACTIONS MODULE
# Handles CRUD operations for the user's main transaction ledger.
# Includes pagination, searching, filtering, and auto-categorization hooks.
# ==========================================

# View for fetching latest 10 transactions
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transactions(request):
    transactions = Transaction.objects.filter(user=request.user).select_related('category').order_by('-date', '-created_at')[:10]  # Fetch latest 10 transactions

    data = [
        {
            "id": t.id,
            "category_name": t.category.name if t.category else "Other",  # Fetch category name
            "category_type": t.category_type,  # Income or Expense
            "description": t.description,
            "amount": float(t.amount),
            "date": t.date.isoformat(),  # Convert date to JSON format
            "created_at": t.created_at.isoformat(), # Added exact timestamp for sorting
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
        queryset = Transaction.objects.filter(user_id=user.id).order_by('-date', '-created_at')
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


# ==========================================
# 2. CATEGORIES MODULE
# Manages the list of available categories. Auto-provisions the user's account
# with a standard default set of Income and Expense buckets on first load.
# ==========================================

# View for fetching all categories
class CategoryListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CategorySerializer

    def get_queryset(self):
        user = self.request.user
        default_categories = [
            # Expenses
            "Food & Dining", "Transport", "Shopping", "Bills & Utilities",
            "Entertainment", "Health & Medical", "Education", "Rent & Housing",
            "Personal Care", "Travel", "EMI & Loans", "Investments",
            "Gifts & Donations", "Subscriptions", "Miscellaneous",
            # Income
            "Salary", "Freelance", "Business", "Investment Returns",
            "Rental Income", "Bonus", "Other Income",
        ]
        existing_names = set(
            Category.objects.filter(user=user).values_list('name', flat=True)
        )
        # Add any missing categories (works for both new and existing users)
        for name in default_categories:
            if name not in existing_names:
                Category.objects.create(user=user, name=name)
        return Category.objects.filter(user=user).order_by('name')


# ==========================================
# 3. BUDGETING MODULE
# Allows users to set hard limits (`monthly_limit`) on specific categories
# and provides endpoints to query past performance (`BudgetHistory`).
# ==========================================

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


# ==========================================
# 4. AI & AUTOMATIONS MODULE
# Utility endpoints that interface with the machine learning models.
# ==========================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def categorize_description(request):
    """
    Accepts a transaction description and returns the predicted category name.
    Used for live auto-selection in the Add Transaction modal.
    """
    description = request.data.get('description', '').strip()
    if not description:
        return Response({'category': 'Other'})

    try:
        from .categorizer import categorize_transaction
        predicted = categorize_transaction(description)
        return Response({'category': predicted})
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Categorize endpoint error: {e}")
        return Response({'category': 'Other'})
