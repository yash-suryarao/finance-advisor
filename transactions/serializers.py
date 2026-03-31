"""
TRANSACTIONS MODULE - SERIALIZERS (transactions/serializers.py)
---------------------------------------------------------------
Converts financial ledger and budgeting models into JSON payload representations.
"""

from rest_framework import serializers
from .models import Transaction, Budget, BudgetHistory, Category

# ==========================================
# 1. CATEGORY & TRANSACTIONS MODULE
# Serializers mapping base ledger records.
# ==========================================

class CategorySerializer(serializers.ModelSerializer):
    """Serializer for user-defined transaction categories."""
    class Meta:
        model = Category
        fields = '__all__'
        unique_together = ('user', 'name')  

class TransactionSerializer(serializers.ModelSerializer):
    """Serializer for individual financial transactions. Includes joined category name."""
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'date', 'category', 'category_type', 'category_name', 'amount', 'description', 'created_at', 'updated_at']

    def get_category_name(self, obj):
        return obj.category.name if obj.category else "Other"


# ==========================================
# 2. BUDGETING MODULE
# Serializers for active caps and historical tracking.
# ==========================================

class BudgetSerializer(serializers.ModelSerializer):
    """Serializer for setting and retrieving active monthly budget limits."""
    class Meta:
        model = Budget
        fields = ['id', 'user', 'category', 'monthly_limit', 'created_at']
        read_only_fields = ['user']

class BudgetHistorySerializer(serializers.ModelSerializer):
    """Serializer for tracking historical budget performance."""
    class Meta:
        model = BudgetHistory
        fields = '__all__'
