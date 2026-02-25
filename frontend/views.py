from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, F
from datetime import datetime, timedelta
from users.models import User
from transactions.models import Transaction, Category
from group_expenses.models import Settlement
from insights.models import BudgetInsight, SavingsGoal
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.shortcuts import redirect
import json
from django.db.models.functions import ExtractMonth
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

@login_required
def dashboard_stats(request):
    active_users = User.objects.filter(last_login__gte=datetime.now() - timedelta(days=30)).count()

    total_spending = BudgetInsight.objects.aggregate(Sum('average_spending'))['average_spending__sum'] or 1
    forecasted_spending = BudgetInsight.objects.aggregate(Sum('forecasted_spending'))['forecasted_spending__sum'] or 1
    accuracy_rate = round((forecasted_spending / total_spending) * 100, 2) if total_spending else 0

    total_settlements = Settlement.objects.filter(is_settled=True).count()
    total_transactions = Settlement.objects.count()
    support_availability = round((total_settlements / total_transactions) * 100, 2) if total_transactions else 0

    current_month = datetime.now().month
    monthly_savings = SavingsGoal.objects.filter(created_at__month=current_month).aggregate(Sum('saved_amount'))['saved_amount__sum'] or 0

    last_month_savings = SavingsGoal.objects.filter(created_at__month=current_month-1).aggregate(Sum('saved_amount'))['saved_amount__sum'] or 1
    savings_growth = round(((monthly_savings - last_month_savings) / last_month_savings) * 100, 2) if last_month_savings else 0

    investment_users = BudgetInsight.objects.values('user_id').distinct().count()
    investment_users_list = BudgetInsight.objects.values('user_id').distinct()[:5]  # Fetch 5 sample users

    average_roi = BudgetInsight.objects.aggregate(Avg('forecasted_spending'))['forecasted_spending__avg'] or 0

    context = {
        'active_users': active_users,
        'accuracy_rate': accuracy_rate,
        'support_availability': support_availability,
        'monthly_savings': monthly_savings,
        'savings_growth': savings_growth,
        'investment_users': investment_users,
        'investment_users_list': investment_users_list,
        'average_roi': average_roi,
    }

    return render(request, 'homepage.html', context)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def financial_summary(request):
    user = request.user  

    today = datetime.today()
    current_month = today.month
    last_month = (today - timedelta(days=30)).month

    total_balance = Transaction.objects.filter(user=user).aggregate(Sum('amount'))['amount__sum'] or 0

    monthly_income = Transaction.objects.filter(user=user, category_type="income", date__month=current_month).aggregate(Sum('amount'))['amount__sum'] or 0

    monthly_expenses = Transaction.objects.filter(user=user, category_type="expense", date__month=current_month).aggregate(Sum('amount'))['amount__sum'] or 0

    last_month_balance = Transaction.objects.filter(user=user, date__month=last_month).aggregate(Sum('amount'))['amount__sum'] or 1
    balance_change = round(((total_balance - last_month_balance) / last_month_balance) * 100, 2) if last_month_balance else 0

    last_month_income = Transaction.objects.filter(user=user, category_type="income", date__month=last_month).aggregate(Sum('amount'))['amount__sum'] or 0
    income_change = round(((monthly_income - last_month_income) / last_month_income) * 100, 2) if last_month_income else 0

    last_month_expenses = Transaction.objects.filter(user=user, category_type="expense", date__month=last_month).aggregate(Sum('amount'))['amount__sum'] or 0
    expense_change = round(((monthly_expenses - last_month_expenses) / last_month_expenses) * 100, 2) if last_month_expenses else 0

    # Explicit Savings Calculation
    savings = float(monthly_income) - float(monthly_expenses)
    last_month_savings = float(last_month_income) - float(last_month_expenses)
    savings_change = round(((savings - last_month_savings) / abs(last_month_savings)) * 100, 2) if last_month_savings else 0
    savings_rate = round((savings / float(monthly_income)) * 100, 2) if monthly_income > 0 else 0

    # Debt Ratio
    from users.models import FinancialData
    financial_data = FinancialData.objects.filter(user=user).first()
    total_debt = float(financial_data.total_debt) if financial_data else 0
    debt_ratio = round((total_debt / float(monthly_income)) * 100, 2) if monthly_income > 0 else 0

    # Financial Health Score
    if savings_rate > 20 and debt_ratio < 30:
        financial_health_score = 100
        financial_health = 'Excellent'
    elif savings_rate > 10 and debt_ratio < 40:
        financial_health_score = 70
        financial_health = 'Good'
    else:
        financial_health_score = 30
        financial_health = 'Poor'

    total_goal = SavingsGoal.objects.filter(user=user).aggregate(Sum('target_amount'))['target_amount__sum'] or 1
    total_savings = SavingsGoal.objects.filter(user=user).aggregate(Sum('saved_amount'))['saved_amount__sum'] or 0
    savings_progress = round((total_savings / total_goal) * 100, 2) if total_goal else 0

    context = {
        'total_balance': total_balance,
        'balance_change': balance_change,
        'monthly_income': monthly_income,
        'income_change': income_change,
        'monthly_expenses': monthly_expenses,
        'expense_change': expense_change,
        'savings': savings,
        'savings_change': savings_change,
        'savings_rate': savings_rate,
        'debt_ratio': debt_ratio,
        'financial_health': financial_health,
        'financial_health_score': financial_health_score,
        'savings_progress': savings_progress,
    }

    return JsonResponse(context)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def spending_analysis(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)
    user_id = request.user.id
    period = request.GET.get('period', 'month')

    # Determine date range
    today = datetime.today().date()
    if period == 'week':
        start_date = today - timedelta(days=today.weekday())
    elif period == 'year':
        start_date = today.replace(month=1, day=1)
    else:  # Default to month
        start_date = today.replace(day=1)

    transactions = Transaction.objects.filter(user_id=user_id, date__gte=start_date)

    # Group by date
    datewise_income = transactions.filter(category_type="income").values('date').annotate(total=Sum('amount'))
    datewise_expense = transactions.filter(category_type="expense").values('date').annotate(total=Sum('amount'))

    income_dict = {entry['date']: entry['total'] for entry in datewise_income}
    expense_dict = {entry['date']: entry['total'] for entry in datewise_expense}

    # Gather all unique dates where a transaction exists
    unique_dates = sorted(set(income_dict.keys()).union(set(expense_dict.keys())))

    # Prepare chart data explicitly around transaction points
    dates = [d.strftime('%Y-%m-%d') for d in unique_dates]
    income = [income_dict.get(d, 0) for d in unique_dates]
    expenses = [expense_dict.get(d, 0) for d in unique_dates]

    # Expense category breakdown
    expense_categories = transactions.filter(category_type="expense", category__isnull=False).values('category_id').annotate(total=Sum('amount'))
    category_data = [
        {"category": Category.objects.get(id=entry["category_id"]).name, "amount": entry["total"]}
        for entry in expense_categories
    ]

    # Monthly expense trend
    monthly_expenses = transactions.filter(category_type="expense").annotate(month=ExtractMonth('date')).values('month').annotate(total=Sum('amount')).order_by('month')
    months = [f"Month {entry['month']}" for entry in monthly_expenses]
    monthly_totals = [entry['total'] for entry in monthly_expenses]

    # Monthly expense & income trend for 6 months (Income vs Expenses Bar Chart)
    last_6_months = []
    for i in range(5, -1, -1):
        d = today - timedelta(days=i*30)
        last_6_months.append((d.year, d.month, d.strftime('%b %Y')))

    bar_months = []
    bar_income = []
    bar_expenses = []

    for year, month, label in last_6_months:
        inc = transactions.filter(category_type="income", date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or 0
        exp = transactions.filter(category_type="expense", date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or 0
        if label not in bar_months:  # prevent duplicate months if days overlap month boundaries
            bar_months.append(label)
            bar_income.append(float(inc))
            bar_expenses.append(float(exp))

    context = {
        "dates": dates,
        "income": income,
        "expenses": expenses,
        "expense_categories": category_data,
        "months": months,
        "monthly_expenses": monthly_totals,
        "bar_months": bar_months,
        "bar_income": bar_income,
        "bar_expenses": bar_expenses
    }

    return JsonResponse(context)


def login_view(request):
    return render(request, 'frontend/login.html')

def signup_view(request):
    return render(request, 'frontend/signup.html')

@login_required
def dashboard_page(request):
    return render(request, 'frontend/dashboard.html')

@login_required
def transactions_page(request):
    return render(request, 'frontend/transaction.html')

@login_required
def budget_page(request):
    return render(request, 'frontend/budget.html')

@login_required
def saving_goals_page(request):
    return render(request, 'frontend/goals.html')

@login_required
def recurring_payments_page(request):
    return render(request, 'frontend/recurring.html')

@login_required
def group_expenses_page(request):
    return render(request, 'frontend/group_expenses.html')

@login_required
def analysis_page(request):
    return render(request, 'frontend/analysis.html')

@login_required
def profile_page(request):
    return render(request, 'frontend/profile.html')
