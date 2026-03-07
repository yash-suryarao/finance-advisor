from django.urls import path
from .views import (
    get_transactions, TransactionListCreateView, TransactionDetailView, CategoryListView,
    categorize_description
)
from .views import BudgetView, BudgetHistoryView

urlpatterns = [
    # ==========================================
    # 1. CORE TRANSACTIONS
    # ==========================================
    path('', TransactionListCreateView.as_view(), name='transaction_list_create'),
    path('get-transactions/', get_transactions, name='get_transactions'),
    path('<int:pk>/', TransactionDetailView.as_view(), name='transaction_detail'),

    # ==========================================
    # 2. CATEGORIES
    # ==========================================
    path('categories/', CategoryListView.as_view(), name='category_list'),

    # ==========================================
    # 3. BUDGETING
    # ==========================================
    path('budget/', BudgetView.as_view(), name='budget'),
    path('budget-history/', BudgetHistoryView.as_view(), name='budget-history'),

    # ==========================================
    # 4. AI & AUTOMATIONS - CATEGORIZATION
    # ==========================================
    path('categorize/', categorize_description, name='categorize_description'),
]
