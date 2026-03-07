from rest_framework import serializers
from .models import BudgetInsight

# ==========================================
# 1. AI FORECASTING SERIALIZERS
# ==========================================

class BudgetInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = BudgetInsight
        fields = '__all__'