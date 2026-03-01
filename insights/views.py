from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from insights.utils import get_advanced_ai_insights
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import Sum, Avg
from .models import BudgetInsight
from transactions.models import Budget as TransactionsBudget, BudgetHistory, Transaction
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.utils.timezone import now
from datetime import datetime, timedelta
from rest_framework import status

from notifications.models import Notification
from .serializers import BudgetInsightSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_insights(request):
    """
    Generates AI insights based on predictive forecasting and transaction limits.
    """
    # Trigger the new ML Pipeline
    insights = get_advanced_ai_insights(request.user)

    if not insights:
        insights.append({
            "type": "General",
            "title": "Insufficient Data",
            "description": "Start adding transactions and a budget to receive personalized AI financial forecasts.",
            "category": "All",
            "data_point": 0.0,
            "llm_details": "Keep using the app and wait for more data to be collected."
        })

    return Response(insights)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_suggested_budget(request):
    """
    Updates the user's budget with the AI-suggested limit.
    """
    user = request.user
    category = request.data.get("category")
    new_limit = request.data.get("new_limit")

    if not category or not new_limit:
        return Response({"error": "Missing category or new limit"}, status=400)

    budget, created = TransactionsBudget.objects.get_or_create(user_id=user.id, category=category)
    budget.monthly_limit = new_limit
    budget.save()

    return Response({"message": f"Budget updated successfully for {category}!", "new_limit": new_limit})


class BudgetInsightView(generics.ListAPIView):
    serializer_class = BudgetInsightSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BudgetInsight.objects.filter(user=self.request.user)



# 🚀 1️⃣ AI-Powered Smart Recommendations
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_savings_insights(request):
    """Fetch AI-based savings recommendations for the user."""
    user = request.user
    insights = BudgetInsight.objects.filter(user_id=user.id).order_by('-created_at')

    insights_list = [
        {
            "category": insight.category,
            "average_spending": float(insight.average_spending),
            "forecasted_spending": float(insight.forecasted_spending),
            "savings_recommendation": insight.savings_recommendation
        }
        for insight in insights
    ]

    return Response(insights_list, status=status.HTTP_200_OK)

# 🚀 2️⃣ Monthly Savings Projection Chart
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_savings_projections(request):
    """Fetch monthly savings projections based on past spending trends."""
    user = request.user
    current_year = now().year
    current_month = now().month

    # Fetch past budget history (total limits vs actual spent to calculate real savings)
    budget_history = (
        BudgetHistory.objects
        .filter(user=user, year=current_year)
        .values('month')
        .annotate(
            total_budget=Sum('previous_limit'),
            total_spent=Sum('actual_spent')
        )
        .order_by('month')
    )

    # Fetch current budget limit for future projection base
    budget_agg = TransactionsBudget.objects.filter(user=user).aggregate(total=Sum('monthly_limit'))
    current_budget_total = float(budget_agg['total'] or 0)
    
    # Estimate average monthly spend to find average savings
    spend_agg = Transaction.objects.filter(user=user, date__year=current_year).aggregate(avg=Avg('amount'))
    avg_spent = float(spend_agg['avg'] or 0)
    
    projected_monthly_savings = current_budget_total - avg_spent
    if projected_monthly_savings <= 0:
        projected_monthly_savings = current_budget_total * 0.10 # default 10%

    # Prepare projection data
    months = []
    savings_data = []
    cumulative_savings = 0.0

    # Accrue historical
    for entry in budget_history:
        month_name = datetime(current_year, entry['month'], 1).strftime('%b')
        months.append(month_name)
        
        saved_that_month = float(entry['total_budget'] or 0) - float(entry['total_spent'] or 0)
        if saved_that_month < 0: saved_that_month = 0
        
        cumulative_savings += saved_that_month
        savings_data.append(cumulative_savings)

    # Initial historical seed if db is empty
    if not months:
        months.append(datetime(current_year, current_month, 1).strftime('%b'))
        savings_data.append(0.0)

    # Forecast next 12 months
    for i in range(1, 13):
        future_month_val = (current_month + i - 1) % 12 + 1
        future_year_val = current_year + ((current_month + i - 1) // 12)
        future_month_name = datetime(future_year_val, future_month_val, 1).strftime('%b')

        months.append(future_month_name)
        cumulative_savings += projected_monthly_savings
        savings_data.append(cumulative_savings)

    return Response({"months": months, "amounts": savings_data}, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_monthly_savings_history(request):
    """Fetch monthly savings history for the user."""
    user = request.user
    savings_history = (
        BudgetHistory.objects
        .filter(user=user)
        .values('month', 'year')
        .annotate(
            total_saved=Sum('suggested_limit'),
            actual_spent=Sum('actual_spent'),
            previous_limit=Sum('previous_limit')
        )
        .order_by('year', 'month')
    )

    history_list = [
        {
            "month": datetime(year=entry['year'], month=entry['month'], day=1).strftime('%b %Y'),
            "total_saved": float(entry['total_saved'] or 0),
            "actual_spent": float(entry['actual_spent'] or 0),
            "previous_limit": float(entry['previous_limit'] or 0),
        }
        for entry in savings_history
    ]

    return Response(history_list)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """Fetch unread notifications for the user."""
    user = request.user
    notifications = Notifications.objects.filter(user=user, is_read=False).order_by('-created_at')

    notifications_list = [
        {"id": n.id, "message": n.message, "created_at": n.created_at.strftime("%Y-%m-%d %H:%M:%S")}
        for n in notifications
    ]

    return Response(notifications_list)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """Mark all notifications as read."""
    user = request.user
    Notifications.objects.filter(user=user, is_read=False).update(is_read=True)
    return Response({"message": "Notifications marked as read."})
