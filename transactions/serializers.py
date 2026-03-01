from rest_framework import serializers
from .models import Transaction
from .models import Budget,BudgetHistory
from .models import Category


class BudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Budget
        fields = ['id', 'user', 'category', 'monthly_limit', 'created_at']
        read_only_fields = ['user']


class CategorySerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Category
        fields = '__all__'
        unique_together = ('user', 'name')  




class TransactionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = Transaction
        fields = ['id', 'date', 'category', 'category_type', 'category_name', 'amount', 'description', 'created_at', 'updated_at']

class BudgetHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetHistory
        fields = '__all__'


