"""
INSIGHTS MODULE - VIEWS (insights/views.py)
-------------------------------------------
This file contains the API endpoints for all AI-driven financial insights features.
It is organized into four main sections:
1. AI & FORECASTING INSIGHTS: Endpoints for Gemini AI summaries, ML Anomaly Detection, and Budget Trajectories.
2. SAVINGS TRENDS & PROJECTIONS: Endpoints for historical savings and future financial trajectory math.
3. NOTIFICATIONS API: Endpoints to fetch unread system alerts.
4. SAVINGS GOAL MANAGEMENT: Endpoints for adding, updating (depositing), and withdrawing custom savings goals.
"""

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
import pandas as pd

# ==========================================
# 1. AI & FORECASTING INSIGHTS
# These endpoints handle Machine Learning and Gemini LLM features
# ==========================================


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
def monthly_xai_review(request):
    """
    Generates a full Explainable AI Summary covering the entire month.
    """
    from insights.utils import get_user_transactions_df, generate_monthly_xai_report
    user = request.user
    df = get_user_transactions_df(user)
    
    if df.empty:
        return Response({"error": "No transaction data available for analysis."}, status=400)
        
    current_month_str = df['date'].dt.to_period('M').max()
    prev_month_str = current_month_str - 1

    # Extract Income and Spending
    curr_inc = df[(df['date'].dt.to_period('M') == current_month_str) & (df['type'] == 'Income')]['amount'].sum()
    curr_exp = df[(df['date'].dt.to_period('M') == current_month_str) & (df['type'] == 'Expense')]['amount'].sum()
    
    prev_inc = df[(df['date'].dt.to_period('M') == prev_month_str) & (df['type'] == 'Income')]['amount'].sum()
    prev_exp = df[(df['date'].dt.to_period('M') == prev_month_str) & (df['type'] == 'Expense')]['amount'].sum()
    
    # Financial Health Calculation (Mirrors frontend logic)
    savings_rate = round(((curr_inc - curr_exp) / curr_inc) * 100, 2) if curr_inc > 0 else 0
    spending_ratio = round((curr_exp / curr_inc) * 100, 2) if curr_inc > 0 else 0
    savings_score = min(50, max(0, (savings_rate / 20) * 50))
    spending_score = min(50, max(0, ((100 - spending_ratio) / 20) * 50))
    health_score = int(max(0, min(100, savings_score + spending_score)))
    
    # Top 3 Categories
    top_cats = df[(df['date'].dt.to_period('M') == current_month_str) & (df['type'] == 'Expense')].groupby('category')['amount'].sum().nlargest(3).index.tolist()

    user_data_summary = {
        'current_month_income': float(curr_inc),
        'current_month_spending': float(curr_exp),
        'previous_month_income': float(prev_inc),
        'previous_month_spending': float(prev_exp),
        'health_score': health_score,
        'top_categories': top_cats
    }

    ai_report = generate_monthly_xai_report(user_data_summary)
    return Response(ai_report, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_subscriptions(request):
    """
    Extracts recurring subscriptions using Gemini across 90 days.
    """
    from insights.utils import extract_subscriptions
    subs = extract_subscriptions(request.user)
    return Response(subs, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_anomaly_heatmap(request):
    """
    Returns daily spending with anomaly markers.
    """
    from insights.utils import get_user_transactions_df, detect_anomalies
    user = request.user
    df = get_user_transactions_df(user)
    
    if df.empty:
        return Response([])
        
    # Get last 60 days
    sixty_days_ago = pd.Timestamp.now() - pd.Timedelta(days=60)
    df = df[df['date'] >= sixty_days_ago]
    
    if df.empty:
        return Response([])
        
    # Get daily aggregates
    daily_spend = df[df['type'] == 'Expense'].groupby(df['date'].dt.strftime('%Y-%m-%d'))['amount'].sum().to_dict()
    
    # Run the isolation forest
    anomalies = detect_anomalies(user)
    anomaly_dates = [a['title'] for a in anomalies] # Extracted purely for marker
    
    # We rebuild this for the heatmap UI format [date, amount, is_anomaly]
    heatmap_data = []
    
    # Rerun isolation logic locally to get specific dates since the util only returns text currently
    # Just simple stddev here for speed to ensure UI works seamlessly
    amounts = pd.Series(list(daily_spend.values()))
    if not amounts.empty and len(amounts) > 5:
        mean = amounts.mean()
        std = amounts.std()
        threshold = mean + (2 * std)
        
        for date_str, amt in daily_spend.items():
            is_anomaly = amt > threshold
            heatmap_data.append([date_str, float(amt), is_anomaly])
            
    return Response(heatmap_data, status=status.HTTP_200_OK)


# ==========================================
# ANALYSIS PAGE REAL DATA ENDPOINTS
# The following three views power the metric cards, spending trends
# bar chart, and the Prophet ML trajectory on the Analysis page.
# ==========================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_analysis_summary(request):
    """
    Powers the 3 top metric cards on the Analysis page:
    - Total Spent (This Month)
    - Total Budget (Sum of all active limits)
    - AI Savings Prediction (projected savings based on current pace)
    """
    user = request.user
    today = datetime.today()
    current_month = today.month
    current_year = today.year

    # 1. Total Expenses this month
    monthly_expenses = float(
        Transaction.objects.filter(
            user=user, category_type='expense',
            date__year=current_year, date__month=current_month
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    # 2. Total monthly income this month
    monthly_income = float(
        Transaction.objects.filter(
            user=user, category_type='income',
            date__year=current_year, date__month=current_month
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    # 3. Total active budget across all categories
    total_budget = float(
        TransactionsBudget.objects.filter(user=user).aggregate(
            total=Sum('monthly_limit')
        )['total'] or 0
    )

    # 4. AI projected savings —  extrapolate current spending pace to end of month
    days_in_month = (datetime(current_year, current_month % 12 + 1, 1) if current_month < 12 else datetime(current_year + 1, 1, 1)) - timedelta(days=1)
    days_elapsed = max(today.day, 1)
    total_days = days_in_month.day

    # Daily burn rate × remaining days = projected additional spend
    daily_burn = monthly_expenses / days_elapsed
    projected_total_spend = daily_burn * total_days
    projected_savings = round(monthly_income - projected_total_spend, 2)

    return Response({
        'total_spent': monthly_expenses,
        'total_budget': total_budget,
        'projected_savings': projected_savings,
        'monthly_income': monthly_income,
        'days_elapsed': days_elapsed,
        'total_days': total_days,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_spending_trends(request):
    """
    Returns last 6 months of:
    - actual spending (bar)
    - budget limits (dashed line)
    Used to draw the Spending vs Budget Trends ECharts bar chart.
    """
    user = request.user
    today = datetime.today()

    months_labels = []
    actual_spends = []
    budget_limits = []

    for i in range(5, -1, -1):
        # Walk back i months from today
        month = (today.month - 1 - i) % 12 + 1
        year = today.year + ((today.month - 1 - i) // 12)

        import calendar
        label = calendar.month_abbr[month]

        # Actual total expenses for this month
        actual = float(
            Transaction.objects.filter(
                user=user, category_type='expense',
                date__year=year, date__month=month
            ).aggregate(total=Sum('amount'))['total'] or 0
        )

        # Sum of all active budget limits for that month from BudgetHistory
        # Fall back to current budget limits if no history exists yet
        hist_budget = float(
            BudgetHistory.objects.filter(
                user=user, year=year, month=month
            ).aggregate(total=Sum('previous_limit'))['total'] or 0
        )
        if hist_budget == 0:
            # Use current active limits as fallback
            hist_budget = float(
                TransactionsBudget.objects.filter(user=user).aggregate(
                    total=Sum('monthly_limit')
                )['total'] or 0
            )

        months_labels.append(label)
        actual_spends.append(actual)
        budget_limits.append(hist_budget)

    return Response({
        'months': months_labels,
        'actual_spends': actual_spends,
        'budget_limits': budget_limits,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_budget_trajectory(request):
    """
    Powers the Zero-Based Budget Trajectory chart.
    Returns:
    - `actual`: Cumulative real spend for each day of the current month up to today
    - `predicted`: Prophet ML predicted cumulative spend for remaining days
    - `days`: Day labels ['Day 1', 'Day 2', ...]
    - `budget_limit`: Total monthly budget cap (the green reference line)
    """
    from insights.utils import get_user_transactions_df
    user = request.user
    today = datetime.today()
    current_month = today.month
    current_year = today.year
    days_elapsed = today.day

    # Total days in month
    import calendar
    total_days = calendar.monthrange(current_year, current_month)[1]

    # Prepare daily expense data for this month from ORM (fast, no CSV needed)
    daily_qs = (
        Transaction.objects.filter(
            user=user, category_type='expense',
            date__year=current_year, date__month=current_month
        )
        .values('date')
        .annotate(total=Sum('amount'))
        .order_by('date')
    )
    daily_map = {entry['date'].day: float(entry['total']) for entry in daily_qs}

    # Build cumulative actual spend series
    cumulative = 0.0
    actual = []
    for day in range(1, total_days + 1):
        if day <= days_elapsed:
            cumulative += daily_map.get(day, 0.0)
            actual.append(round(cumulative, 2))
        else:
            actual.append(None)  # No data yet for future days

    # Build ML prediction from day_elapsed onward using linear extrapolation
    # Use the daily average burn rate from days elapsed so far as the base rate
    # Prophet forecasting only runs if there's enough history, otherwise we fall back
    predicted = [None] * total_days

    try:
        df = get_user_transactions_df(user)
        if not df.empty and len(df) >= 10:
            try:
                from prophet import Prophet
                # Use last 60 days of daily spend to build a reliable Prophet model
                sixty_days_ago = pd.Timestamp.now() - pd.Timedelta(days=60)
                hist_df = df[(df['type'] == 'Expense') & (df['date'] >= sixty_days_ago)].copy()
                if len(hist_df) >= 5:
                    daily_hist = hist_df.groupby(hist_df['date'].dt.date)['amount'].sum().reset_index()
                    daily_hist.columns = ['ds', 'y']
                    daily_hist['ds'] = pd.to_datetime(daily_hist['ds'])

                    m = Prophet(daily_seasonality=False, yearly_seasonality=False, weekly_seasonality=True)
                    m.fit(daily_hist)

                    # Predict the remaining days this month
                    future_dates = pd.date_range(
                        start=datetime(current_year, current_month, days_elapsed),
                        end=datetime(current_year, current_month, total_days)
                    )
                    future_df = pd.DataFrame({'ds': future_dates})
                    forecast = m.predict(future_df)

                    # Convert to cumulative, starting from the last actual cumulative value
                    last_actual = actual[days_elapsed - 1] or 0.0
                    pred_cum = last_actual

                    # Set anchor point at day_elapsed (same as last actual)
                    predicted[days_elapsed - 1] = round(last_actual, 2)
                    for idx, row in forecast.iloc[1:].iterrows():
                        pred_cum += max(0, row['yhat'])
                        day_num = row['ds'].day
                        if 1 <= day_num <= total_days:
                            predicted[day_num - 1] = round(pred_cum, 2)
            except Exception:
                # Prophet unavailable, fall back to linear extrapolation
                pass
    except Exception:
        pass

    # Linear extrapolation fallback if Prophet didn't populate predictions
    if all(v is None for v in predicted[days_elapsed:]):
        last_actual_val = actual[days_elapsed - 1] or 0.0
        daily_avg = last_actual_val / days_elapsed if days_elapsed > 0 else 0
        predicted[days_elapsed - 1] = round(last_actual_val, 2)  # anchor
        running = last_actual_val
        for day in range(days_elapsed, total_days):
            running += daily_avg
            predicted[day] = round(running, 2)

    # Budget cap (total monthly limit)
    total_budget = float(
        TransactionsBudget.objects.filter(user=user).aggregate(
            total=Sum('monthly_limit')
        )['total'] or 0
    )

    return Response({
        'days': [f'Day {i}' for i in range(1, total_days + 1)],
        'actual': actual,
        'predicted': predicted,
        'budget_limit': total_budget,
    }, status=status.HTTP_200_OK)


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

# ==========================================
# 2. SAVINGS TRENDS & PROJECTIONS
# These endpoints calculate historical savings data and project future savings 
# based on the user's current spending habits and limits.
# ==========================================

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

# ==========================================
# 3. NOTIFICATIONS API
# Handles fetching the notification alerts generated by the system (e.g. overspending alerts).
# ==========================================

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

# ==========================================
# 4. SAVINGS GOAL MANAGEMENT 
# Manages the lifecycle of user-defined Savings Goals (Create, Deposit, Withdraw, Delete)
# ==========================================

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


# --- Notifications API (Cont.) ---
# Moved down here previously, this endpoint handles marking unread notifications as read.

# Mark notifications as read
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notifications_read(request):
    """Mark all notifications as read."""
    user = request.user
    Notifications.objects.filter(user=user, is_read=False).update(is_read=True)
    return Response({"message": "Notifications marked as read."})
