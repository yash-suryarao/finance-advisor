from django.urls import path
from .views import (
    process_voice_entry, confirm_voice_transaction, get_transactions, upcoming_bills,
    export_transactions_csv, TransactionListCreateView, TransactionDetailView, CategoryListView, upload_receipt
)
from .views import CurrencyConverter
from .views import BudgetView, BudgetHistoryView

urlpatterns = [
    path('', TransactionListCreateView.as_view(), name='transaction_list_create'),
    path('upload-receipt/', upload_receipt, name='upload_receipt'),
    path('process-voice-entry/', process_voice_entry, name='process_voice_entry'),
    path('confirm-voice-transaction/', confirm_voice_transaction, name='confirm_voice_transaction'),
    path('get-transactions/', get_transactions, name='get_transactions'),
    path('upcoming-bills/', upcoming_bills, name='upcoming-bills'),
    path('export-transactions-csv/', export_transactions_csv, name='export_transactions_csv'),
    path('<int:pk>/', TransactionDetailView.as_view(), name='transaction_detail'),
    path('categories/', CategoryListView.as_view(), name='category_list'),
    path('currency-convert/', CurrencyConverter.as_view(), name='currency-converter'),
    path('budget/', BudgetView.as_view(), name='budget'),
    path('budget-history/', BudgetHistoryView.as_view(), name='budget-history'),
]
