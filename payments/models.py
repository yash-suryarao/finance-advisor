# payments/models.py
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
import uuid
User = get_user_model()

class Payment(models.Model):
    payment_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    status = models.CharField(max_length=50, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.amount}"




class RecurringPayment(models.Model):
    CATEGORY_CHOICES = [
        ('entertainment', 'Entertainment'),
        ('bills', 'Bills'),
        ('rent', 'Rent'),
        ('insurance', 'Insurance'),
        ('others', 'Others'),
    ]

    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)  # Links payment to a user
    name = models.CharField(max_length=255)  # Payment name (e.g., Netflix, Rent)
    amount = models.DecimalField(max_digits=10, decimal_places=2)  # Payment amount
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES)  # Payment category
    frequency = models.CharField(max_length=50, choices=FREQUENCY_CHOICES)  # Payment frequency
    next_payment_date = models.DateField()  # Next due date
    status = models.CharField(
        max_length=20,
        choices=[('active', 'Active'), ('paused', 'Paused'), ('canceled', 'Canceled')],
        default='active'
    )

    created_at = models.DateTimeField(auto_now_add=True)  # Timestamp when payment was created
    updated_at = models.DateTimeField(auto_now=True)  # Timestamp when payment was last updated

    def __str__(self):
        return f"{self.name} - {self.amount}"
