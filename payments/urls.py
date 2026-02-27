from django.urls import path
from .views import RecurringPaymentListCreateView, RecurringPaymentUpdateDeleteView

urlpatterns = [
    path('recurring-payments/', RecurringPaymentListCreateView.as_view(), name='recurring_payments'),
    path('recurring-payments/<int:pk>/', RecurringPaymentUpdateDeleteView.as_view(), name='recurring_payment_detail'),
]
