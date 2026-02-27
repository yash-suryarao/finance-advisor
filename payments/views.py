
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Payment
from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from .models import RecurringPayment
from .serializers import RecurringPaymentSerializer
from celery import shared_task
from django.utils.timezone import now
from notifications.models import Notification





# ✅ List all recurring payments for the logged-in user & create a new payment
class RecurringPaymentListCreateView(generics.ListCreateAPIView):
    serializer_class = RecurringPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RecurringPayment.objects.filter(user=self.request.user)  # Only return user's payments

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)  # Assign logged-in user to new payment


# ✅ Retrieve, Update, or Delete a payment (only for the owner)
class RecurringPaymentUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = RecurringPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return RecurringPayment.objects.filter(user=self.request.user)



@shared_task
def send_payment_reminders():
    today = now().date()
    upcoming_payments = RecurringPayment.objects.filter(next_payment_date=today)

    for payment in upcoming_payments:
        Notification.objects.create(
            user=payment.user,
            message=f"Reminder: {payment.name} payment of ${payment.amount} is due today!"
        )
