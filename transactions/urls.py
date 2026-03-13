"""
TRANSACTIONS MODULE - URLS (transactions/urls.py)
-------------------------------------------------
This file defines the URL routing for the transactions app APIs.
It maps endpoints to the views defined in `transactions/views.py`.
"""

from django.urls import path
from .views import (
    get_transactions, TransactionListCreateView, TransactionDetailView, CategoryListView,
    categorize_description
)
from .views import BudgetView, BudgetHistoryView

urlpatterns = [
    # ==========================================
    # 1. CORE TRANSACTIONS
    # Endpoints for Ledger CRUD and fetching single records.
    # ==========================================
    path('', TransactionListCreateView.as_view(), name='transaction_list_create'),
    path('get-transactions/', get_transactions, name='get_transactions'),
    path('<int:pk>/', TransactionDetailView.as_view(), name='transaction_detail'),

    # ==========================================
    # 2. CATEGORIES
    # Endpoints to list and auto-provision user spending categories.
    # ==========================================
    path('categories/', CategoryListView.as_view(), name='category_list'),

    # ==========================================
    # 3. BUDGETING
    # Endpoints to manage active budgets and view past performance.
    # ==========================================
    path('budget/', BudgetView.as_view(), name='budget'),
    path('budget-history/', BudgetHistoryView.as_view(), name='budget-history'),

    # ==========================================
    # 4. AI & AUTOMATIONS - CATEGORIZATION
    # Endpoints to interface with the Local ML model for transaction tagging.
    # ==========================================
    path('categorize/', categorize_description, name='categorize_description'),
]
