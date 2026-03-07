from rest_framework import serializers
from .models import Transaction, Budget, BudgetHistory, Category

# ==========================================
# 1. CATEGORY & TRANSACTIONS MODULE
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


# ==========================================
# 2. BUDGETING MODULE
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
