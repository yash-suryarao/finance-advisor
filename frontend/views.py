from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, F
from datetime import datetime, timedelta
from users.models import User
from transactions.models import Transaction, Category
from insights.models import BudgetInsight
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

    total_settlements = 0
    total_transactions = 0
    support_availability = 0

    current_month = datetime.now().month
    monthly_savings = 0
    last_month_savings = 1
    savings_growth = 0

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
    current_year = today.year
    
    # Calculate exactly one month ago
    last_month_date = today.replace(day=1) - timedelta(days=1)
    last_month = last_month_date.month
    last_month_year = last_month_date.year

    def get_net_balance(qs):
        income = qs.filter(category_type="income").aggregate(Sum('amount'))['amount__sum'] or 0
        expense = qs.filter(category_type="expense").aggregate(Sum('amount'))['amount__sum'] or 0
        return float(income) - float(expense)

    def calc_progress(current, target):
        if target == 0:
            if current == 0:
                return 0.00
            elif current > 0:
                return 100.00
            else:
                return -100.00
        return round((float(current) / abs(target)) * 100, 2)

    total_transactions_count = Transaction.objects.filter(user=user).count()

    # Total Balance (All time)
    total_balance = get_net_balance(Transaction.objects.filter(user=user))
    total_income = float(Transaction.objects.filter(user=user, category_type="income").aggregate(Sum('amount'))['amount__sum'] or 0)
    balance_change = round((total_balance / total_income) * 100, 2) if total_income > 0 else 0.00

    # Current Month Actuals
    current_month_qs = Transaction.objects.filter(user=user, date__year=current_year, date__month=current_month)
    monthly_income = float(current_month_qs.filter(category_type="income").aggregate(Sum('amount'))['amount__sum'] or 0)
    monthly_expenses = float(current_month_qs.filter(category_type="expense").aggregate(Sum('amount'))['amount__sum'] or 0)

    # Last Month Baseline
    last_month_qs = Transaction.objects.filter(user=user, date__year=last_month_year, date__month=last_month)
    last_month_income = float(last_month_qs.filter(category_type="income").aggregate(Sum('amount'))['amount__sum'] or 0)
    last_month_expenses = float(last_month_qs.filter(category_type="expense").aggregate(Sum('amount'))['amount__sum'] or 0)

    income_change = calc_progress(monthly_income, last_month_income)
    expense_change = calc_progress(monthly_expenses, last_month_expenses)

    # Explicit Savings Calculation
    savings = monthly_income - monthly_expenses
    last_month_savings = last_month_income - last_month_expenses
    savings_change = calc_progress(savings, last_month_savings)
    savings_rate = round((savings / monthly_income) * 100, 2) if monthly_income > 0 else 0.00

    # Debt Ratio (Debt-to-Income / DTI)
    from users.models import FinancialData
    from django.db.models import Q
    
    financial_data = FinancialData.objects.filter(user=user).first()
    
    # 1. Base monthly loan/debt payments from user's financial profile
    monthly_loans = float(financial_data.loans) if financial_data else 0
    
    # 2. Add actual transaction debt payments from the current month
    actual_debt_payments = last_month_qs.filter(
        Q(category__name__icontains='loan') | 
        Q(category__name__icontains='emi') | 
        Q(category__name__icontains='mortgage') |
        Q(category__name__icontains='credit') |
        Q(description__icontains='loan') |
        Q(description__icontains='emi')
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    total_monthly_debt = monthly_loans + float(actual_debt_payments)
    
    # Calculate DTI Ratio percentage
    debt_ratio = round((total_monthly_debt / monthly_income) * 100, 2) if monthly_income > 0 else 0.00

    # Financial Health Score
    if total_transactions_count == 0:
        financial_health_score = 0
        financial_health = ''
    else:
        if savings_rate > 20 and debt_ratio < 30:
            financial_health_score = 100
            financial_health = 'Excellent'
        elif savings_rate > 10 and debt_ratio < 40:
            financial_health_score = 70
            financial_health = 'Good'
        else:
            financial_health_score = 30
            financial_health = 'Poor'

    total_goal = 1
    total_savings = 0
    savings_progress = 0

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
    # Note: THIS SHOULD ALWAYS use the full base query (all records) or else old records 
    # are hidden by the 'start_date' period filter above it!
    base_transactions = Transaction.objects.filter(user_id=user_id)
    
    last_6_months = []
    # Build a stable month-by-month list
    for i in range(5, -1, -1):
        target_date = today.replace(day=1) - timedelta(days=i*30)
        # Fix date math slightly to get correct year/month pairs jumping back
        month = (today.month - 1 - i) % 12 + 1
        year = today.year + ((today.month - 1 - i) // 12)
        import calendar
        month_abbr = calendar.month_abbr[month]
        last_6_months.append((year, month, f"{month_abbr} {year}"))

    bar_months = []
    bar_income = []
    bar_expenses = []

    for year, month, label in last_6_months:
        inc = base_transactions.filter(category_type="income", date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or 0
        exp = base_transactions.filter(category_type="expense", date__year=year, date__month=month).aggregate(total=Sum('amount'))['total'] or 0
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


def analysis_page(request):
    return render(request, 'frontend/analysis.html')

@login_required
def profile_page(request):
    return render(request, 'frontend/profile.html')
