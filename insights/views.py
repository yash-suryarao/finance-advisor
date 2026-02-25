from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from insights.utils import get_spending_insights, predict_future_spending, suggest_savings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from .models import SavingsGoal
from insights.utils import track_savings_progress
from django.db.models import Sum, Avg
from .models import BudgetInsight
from transactions.models import Budget as TransactionsBudget, BudgetHistory, Transaction
from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.utils.timezone import now
from datetime import datetime, timedelta
from django.db.models import Sum
from rest_framework import status

from notifications.models import Notification
from django.utils.timezone import now
from .serializers import BudgetInsightSerializer

@login_required
def spending_insights_view(request):
    """API to get spending insights."""
    insights = get_spending_insights(request.user)
    return JsonResponse({"spending_insights": insights}, safe=False)

@login_required
def forecast_spending_view(request, category):
    """API to predict future spending for a given category."""
    forecast = predict_future_spending(request.user, category)
    return JsonResponse({"forecasted_spending": forecast})

@login_required
def savings_suggestions_view(request):
    """API to provide cost-saving recommendations."""
    suggestions = suggest_savings(request.user)
    return JsonResponse({"savings_recommendations": suggestions})



@csrf_exempt
@login_required
def add_savings_goal(request):
    """API to create a new savings goal."""
    if request.method == "POST":
        data = json.loads(request.body)
        goal = SavingsGoal.objects.create(
            user=request.user,
            goal_name=data["goal_name"],
            target_amount=data["target_amount"],
            deadline=datetime.strptime(data["deadline"], "%Y-%m-%d").date()
        )
        return JsonResponse({"message": "Goal created successfully!", "goal_id": goal.id})

@login_required
def get_savings_progress(request):
    """API to fetch user's savings goals and progress."""
    track_savings_progress(request.user)  # Auto-update progress
    goals = SavingsGoal.objects.filter(user=request.user).values()
    return JsonResponse({"goals": list(goals)}, safe=False)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_goal_savings(request):
    """API to manually update savings for a goal."""
    user = request.user
    goal_id = request.data.get("goal_id")
    saved_amount = request.data.get("saved_amount")

    try:
        goal = SavingsGoal.objects.get(id=goal_id, user=user)
        goal.saved_amount = saved_amount
        goal.save()

        # Check if goal is completed
        if goal.saved_amount >= goal.target_amount:
            Notifications.objects.create(
                user=user,
                message=f"🎉 Congratulations! You have completed your savings goal: {goal.goal_name}",
                created_at=now(),
                is_read=False
            )

        return Response({"message": "Goal updated successfully."})
    except SavingsGoal.DoesNotExist:
        return Response({"error": "Goal not found."}, status=404)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_insights(request):
    """
    Generates AI insights based on predictive forecasting and transaction limits.
    """
    user = request.user
    last_30_days = now() - timedelta(days=30)
    insights = []

    # Get actual spends per category over the last 30 days
    spending_data = (
        Transaction.objects.filter(user=user, date__gte=last_30_days)
        .values('category__name')
        .annotate(total_spent=Sum('amount'))
    )
    
    budgets = TransactionsBudget.objects.filter(user=user)
    budget_dict = {b.category: float(b.monthly_limit) for b in budgets}

    for spend in spending_data:
        category = spend['category__name'] or "Uncategorized"
        total_spent = float(spend['total_spent'] or 0)
        
        limit = budget_dict.get(category, 0.0)
        if limit == 0.0:
            continue
            
        # Predict future spend for the next 30 days
        projected = predict_future_spending(user, category)
        try:
            projected_val = float(projected)
            # Add current spending and forecasted difference for a complete 30-day window expectation
            expected_total = total_spent + (projected_val / 2) # simplified logic
        except ValueError:
            expected_total = total_spent
             
        suggested = limit * 0.9 if total_spent > limit else limit
        
        if total_spent > limit:
            insights.append({
                "title": f"Overspending in {category}",
                "message": f"You spent ₹{total_spent:.2f}, exceeding your ₹{limit:.2f} budget.",
                "suggested_budget": round(suggested, 2),
                "category": category,
                "action_url": "#"
            })
        elif expected_total > limit:
            insights.append({
                "title": f"Predicted Overspending in {category}",
                "message": f"You are at ₹{total_spent:.2f}. At your AI forecasted pace, you may hit ₹{expected_total:.2f} (Budget: ₹{limit:.2f}).",
                "suggested_budget": round(limit, 2),
                "category": category,
                "action_url": "/budget/"
            })
        else:
            insights.append({
                "title": f"Good Budget Control in {category}",
                "message": f"You are well within your ₹{limit:.2f} budget. Projected total spend: ₹{expected_total:.2f}.",
                "suggested_budget": round(suggested, 2),
                "category": category,
                "action_url": "#"
            })

    # Generic insights fallback
    if not insights:
        insights.append({
            "title": "Insufficient Data",
            "message": "Start adding transactions and a budget to receive personalized AI financial forecasts.",
            "suggested_budget": 0,
            "category": "All",
            "action_url": "/dashboard/"
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
