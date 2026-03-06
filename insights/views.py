from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from insights.utils import get_advanced_ai_insights
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import Sum, Avg
from .models import BudgetInsight, SavingsGoal
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
    Returns category-wise ML insights. LLM summaries are NOT generated here.
    They are fetched lazily via the category_insight_detail endpoint on user click.
    """
    insights = get_advanced_ai_insights(request.user)

    if not insights:
        insights.append({
            "type": "General",
            "title": "Insufficient Data",
            "description": "Start adding transactions and a budget to receive personalized AI financial forecasts.",
            "category": "All",
            "data_point": 0.0,
            "llm_details": ""
        })

    return Response(insights)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def category_insight_detail(request):
    """
    On-demand LLM insight for a SINGLE category (called when user clicks 'View Details').
    Only fires one Gemini API call, preventing free-tier quota exhaustion.
    """
    from insights.utils import get_user_transactions_df, generate_category_llm_insight, detect_anomalies, forecast_spending, suggest_smart_budgets
    import pandas as pd
    
    category = request.GET.get('category', '').strip()
    if not category:
        return Response({'error': 'Category name is required.'}, status=400)

    user = request.user
    df = get_user_transactions_df(user)
    if df.empty:
        return Response({'llm_details': 'No transaction data found for analysis.'})

    # Filter to just this category's expenses
    cat_df = df[(df['category'] == category) & (df['type'] == 'Expense')]
    if cat_df.empty:
        return Response({'llm_details': f'No expense data found for category: {category}'})

    current_month_str = df['date'].dt.to_period('M').max()
    prev_month_str = current_month_str - 1

    curr_total = cat_df[cat_df['date'].dt.to_period('M') == current_month_str]['amount'].sum()
    prev_total = cat_df[cat_df['date'].dt.to_period('M') == prev_month_str]['amount'].sum()
    pct_change = ((curr_total - prev_total) / prev_total * 100) if prev_total > 0 else (100 if curr_total > 0 else 0)

    anomalies = detect_anomalies(user)
    forecasts = forecast_spending(user)
    budgets = suggest_smart_budgets(user)

    anomaly_map = {a['category']: a for a in anomalies}
    forecast_map = {f['category']: f for f in forecasts}
    budget_map = {b['category']: b for b in budgets}

    category_data = {
        'category': category,
        'current_month_spending': float(curr_total),
        'previous_month_spending': float(prev_total),
        'percentage_change': float(round(pct_change, 2)),
        'anomaly_flag': category in anomaly_map,
        'anomaly_details': anomaly_map[category]['description'] if category in anomaly_map else 'None',
        'forecasted_next_month_spending': float(forecast_map.get(category, {}).get('data_point', 0.0)),
        'recommended_budget_limit': float(budget_map.get(category, {}).get('data_point', 0.0)),
    }

    llm_summary = generate_category_llm_insight(category_data)
    return Response({'llm_details': llm_summary})

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



# 1. AI-Powered Smart Recommendations
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

# 2. Monthly Savings Projection Chart
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



# View for Savings Goal
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_savings_goal(request):
    """API to create a new savings goal."""
    data = request.data
    goal = SavingsGoal.objects.create(
        user=request.user,
        goal_name=data.get("goal_name"),
        target_amount=data.get("target_amount"),
        deadline=datetime.strptime(data.get("deadline"), "%Y-%m-%d").date()
    )
    return Response({"message": "Goal created successfully!", "goal_id": goal.id})


# Saving goal progress
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_savings_progress(request):
    """API to fetch user's savings goals and progress (excluding withdrawn goals)."""
    goals = SavingsGoal.objects.filter(user=request.user).exclude(status="Withdrawn").values()
    return Response({"goals": list(goals)})

from transactions.models import Transaction
from django.db.models import Sum
from django.utils.timezone import now

# Update savings goal (Deposit button)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_goal_savings(request):
    """API to add deposit to a savings goal."""
    goal_id = request.data.get("goal_id")
    deposit_amount = request.data.get("deposit_amount")
    
    try:
        deposit_amount = float(deposit_amount)
        if deposit_amount <= 0:
            return Response({"error": "Invalid deposit amount."}, status=400)
            
        # Calculate current net balance
        income = Transaction.objects.filter(user=request.user, category_type="income").aggregate(Sum('amount'))['amount__sum'] or 0
        expense = Transaction.objects.filter(user=request.user, category_type="expense").aggregate(Sum('amount'))['amount__sum'] or 0
        balance = float(income) - float(expense)
        
        if balance < deposit_amount:
            return Response({"error": f"Insufficient balance! You only have ₹{balance:.2f} available."}, status=400)

        goal = SavingsGoal.objects.get(id=goal_id, user=request.user)
        
        # Deduct deposit amount from main balance by logging it as an expense
        Transaction.objects.create(
            user=request.user,
            amount=deposit_amount,
            category_type="expense",
            date=now().date(),
            description=f"Deposit to Savings Goal: {goal.goal_name}"
        )
        
        goal.saved_amount = float(goal.saved_amount) + deposit_amount
        goal.update_progress()
        goal.save()
        return Response({"message": "Deposit added successfully.", "saved_amount": goal.saved_amount})
    except SavingsGoal.DoesNotExist:
        return Response({"error": "Goal not found."}, status=404)
    except (ValueError, TypeError):
        return Response({"error": "Invalid deposit amount."}, status=400)

# Withdraw completed savings goal
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw_goal_savings(request):
    """API to withdraw a saved goal back into the main balance."""
    goal_id = request.data.get("goal_id")
    try:
        goal = SavingsGoal.objects.get(id=goal_id, user=request.user)
        
        if goal.saved_amount < goal.target_amount:
            return Response({"error": "You must reach your target goal before withdrawing."}, status=400)
            
        if goal.status == "Withdrawn":
            return Response({"error": "This goal has already been withdrawn."}, status=400)
            
        # Add the saved money back into the main balance by logging it as Income
        if goal.saved_amount > 0:
            Transaction.objects.create(
                user=request.user,
                amount=goal.saved_amount,
                category_type="income",
                date=now().date(),
                description=f"Withdrawal from Savings Goal: {goal.goal_name}"
            )
            
        goal.status = "Withdrawn"
        goal.save()
        return Response({"message": "Goal successfully withdrawn and funds transferred to balance. Goal preserved in history."})
    except SavingsGoal.DoesNotExist:
        return Response({"error": "Goal not found."}, status=404)

# Delete savings goal
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_savings_goal(request, goal_id):
    """API to delete a savings goal."""
    try:
        goal = SavingsGoal.objects.get(id=goal_id, user=request.user)
        goal.delete()
        return Response({"message": "Goal deleted successfully."})
    except SavingsGoal.DoesNotExist:
        return Response({"error": "Goal not found."}, status=404)



# Mark notifications as read
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """Mark all notifications as read."""
    user = request.user
    Notifications.objects.filter(user=user, is_read=False).update(is_read=True)
    return Response({"message": "Notifications marked as read."})
