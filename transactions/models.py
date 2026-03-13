"""
TRANSACTIONS MODULE - MODELS (transactions/models.py)
-----------------------------------------------------
This file defines the database schema for the financial ledger and budgeting system.
It is organized into three main sections:
1. CATEGORY & TRANSACTIONS MODULE: Core ledger entries (Transaction) and custom tags (Category).
2. BUDGETING MODULE: Active monthly spending limits (Budget) and historical tracking (BudgetHistory).
3. ALERTS & NOTIFICATIONS MODULE: Triggered system alerts related to transactions.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from datetime import datetime
import uuid

User = get_user_model()

# ==========================================
# 1. CATEGORY & TRANSACTIONS MODULE
# Represents the core financial ledger, linking records to users and categories.
# Includes an audit log (DeletedTransaction) for recovery.
# ==========================================

class Category(models.Model):
    """User-defined transaction categories (e.g., Food, Transport, Salary)."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('user', 'name')
        
    def __str__(self):
        return f"{self.user.username} - {self.name}"

class Transaction(models.Model):
    """Individual financial transactions recorded by the user."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    category_type = models.CharField(max_length=50, choices=[('income', 'Income'), ('expense', 'Expense')], default='expense')
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    created_at = models.DateTimeField(default=datetime.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount} ({self.category})"

class DeletedTransaction(models.Model):
    """Log of deleted transactions for auditing or recovery purposes."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    category_name = models.CharField(max_length=100, null=True, blank=True)
    category_type = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)
    date = models.DateField()
    deleted_at = models.DateTimeField(default=datetime.now)

    def __str__(self):
        return f"Deleted: {self.user.username} - {self.amount} ({self.category_name})"


# ==========================================
# 2. BUDGETING MODULE
# Represents active monthly goals and tracks performance over time.
# ==========================================

class Budget(models.Model):
    """User-defined monthly spending limits per category."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=255)
    monthly_limit = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

class BudgetHistory(models.Model):
    """Historical tracking of budget performance month-over-month."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=255)
    month = models.IntegerField()  # Stores the month (1-12)
    year = models.IntegerField()  # Stores the year (2023, 2024, etc.)
    previous_limit = models.DecimalField(max_digits=10, decimal_places=2)
    actual_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    suggested_limit = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        unique_together = ('user', 'category', 'month', 'year')  # Prevents duplicate records


# ==========================================
# 3. ALERTS & NOTIFICATIONS MODULE
# Deprecated/isolated alerts specifically for transaction anomalies.
# Currently largely superseded by the main `notifications` app.
# ==========================================

class alerts(models.Model):
    """User notifications (e.g., nearing budget limit, large expense warning)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transaction_alerts')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.message}"
