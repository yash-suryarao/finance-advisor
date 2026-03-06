from django.urls import path
from .views import (
    get_transactions, TransactionListCreateView, TransactionDetailView, CategoryListView,
    categorize_description
)
from .views import BudgetView, BudgetHistoryView

urlpatterns = [
    path('', TransactionListCreateView.as_view(), name='transaction_list_create'),
    path('get-transactions/', get_transactions, name='get_transactions'),
    path('<int:pk>/', TransactionDetailView.as_view(), name='transaction_detail'),
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('categorize/', categorize_description, name='categorize_description'),
    path('budget/', BudgetView.as_view(), name='budget'),
    path('budget-history/', BudgetHistoryView.as_view(), name='budget-history'),
]
