from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.db.models import Sum, Count
from django.utils.timezone import now
from .models import AdminSettings
from transactions.models import Transaction
from payments.models import Payment
from notifications.models import Notification
from users.models import User
import csv
import json
from django.db.models import Q
from datetime import datetime, timedelta, date
from django.utils.safestring import mark_safe
from collections import defaultdict
from django.db.models.functions import TruncMonth
from django.db.models import Sum, Case, When, DecimalField
from django.utils.timezone import now


@login_required
def admin_dashboard(request):
    today = date.today()
    try:
        filters = json.loads(request.body)
    except json.JSONDecodeError:
        filters = {}

    payments = Payment.objects.all()
    users = User.objects.all()
    transactions = Transaction.objects.all()

    # Apply Date Filter
    if filters.get("start_date") and filters.get("end_date"):
        payments = payments.filter(created_at__range=[filters["start_date"], filters["end_date"]])

    # Apply User Type Filter
    # Removed as is_premium no longer exists

    # Apply Transaction Type Filter
    if filters.get("transaction_type"):
        transactions = transactions.filter(category_type=filters["transaction_type"])

    # Apply Payment Status Filter
    if filters.get("payment_status"):
        payments = payments.filter(status=filters["payment_status"])

    # Total Revenue
    total_revenue = Transaction.objects.aggregate(Sum('amount'))['amount__sum'] or 0

    # Total Users
    total_users = User.objects.count()

    # Total Transactions
    total_transactions = Transaction.objects.count()

    total_payments_completed = Payment.objects.filter(status='Completed').count()

    # Revenue Data
    revenue_data = payments.annotate(month=TruncMonth('created_at')).values('month').annotate(total=Sum('amount')).order_by('month')
    months = [item['month'].strftime('%Y-%m') if item['month'] else '' for item in revenue_data]
    revenue_values = [float(item['total']) if item['total'] else 0 for item in revenue_data]

    # User Distribution Data
    user_distribution = []

    # Transactions by Category
    transaction_data = list(transactions.values('category_type').annotate(total=Count('id')))

    # Payment Status Data
    payment_status_data = list(payments.values('status').annotate(count=Count('payment_id')))

    context = {
        'total_revenue': total_revenue,
        'total_users': total_users,
        'total_transactions': total_transactions,
        'total_payments_completed': total_payments_completed,
        'months': months,
        'revenue_data': revenue_values,
        'user_distribution': user_distribution,
        'transaction_data': transaction_data,
        'payment_status_data': payment_status_data,
    }

    return render(request, 'admin_dashboard/index.html', context)



@login_required
def user_management(request):
    query = request.GET.get('query', '').strip()
    status_filter = request.GET.get('status', '')
    sort_by = request.GET.get('sort', 'username')  # Default sorting by username
    order = request.GET.get('order', 'asc')  # 'asc' or 'desc'
    
    users = User.objects.all()

    # Search Query Filter (Username & Email)
    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))

    # Status Filter (Active, Banned, Pending)
    if status_filter:
        if status_filter == "active":
            users = users.filter(is_active=True)
        elif status_filter == "banned":
            users = users.filter(is_active=False)

    # Sorting (Name, Email, Last Login)
    order_by = sort_by if order == 'asc' else f'-{sort_by}'
    users = users.order_by(order_by)

    # Pagination
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 10))
    start = (page - 1) * page_size
    end = start + page_size
    total_users = users.count()

    context = {
        "users": users[start:end],
        "total_users": total_users,
        "active_users": User.objects.filter(is_active=True).count(),
        "banned_users": User.objects.filter(is_active=False).count(),
        "page": page,
        "page_size": page_size,
        "sort_by": sort_by,
        "order": order,
        "query": query,
        "status_filter": status_filter,
    }
    return render(request, "admin_dashboard/user_management.html", context)

@login_required
def export_users(request):
    """ Export users data as CSV based on applied filters """
    query = request.GET.get('query', '').strip()
    status_filter = request.GET.get('status', '')
    
    users = User.objects.all()

    if query:
        users = users.filter(Q(username__icontains=query) | Q(email__icontains=query))

    if status_filter:
        if status_filter == "active":
            users = users.filter(is_active=True)
        elif status_filter == "banned":
            users = users.filter(is_active=False)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="users.csv"'
    
    writer = csv.writer(response)
    writer.writerow(["Username", "Email", "Status", "Last Login"])
    
    for user in users:
        writer.writerow([user.username, user.email, "Active" if user.is_active else "Inactive", user.last_login])

    return response

@login_required
def update_user(request, user_id):
    """ Update user details via AJAX """
    if request.method == "POST":
        try:
            user = get_object_or_404(User, id=user_id)
            data = request.POST
            
            user.username = data.get("username", user.username)
            user.email = data.get("email", user.email)
            user.is_superuser = data.get("is_superuser") == "True"
            user.save()

            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request"})

@login_required
def bulk_delete_users(request):
    """ Bulk delete selected users """
    if request.method == "POST":
        try:
            user_ids = request.POST.getlist("user_ids[]")
            User.objects.filter(id__in=user_ids).delete()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})
    return JsonResponse({"success": False, "error": "Invalid request"})

@login_required
def transaction_management(request):
    transactions = Transaction.objects.all().order_by('-date')

    # Get filter values from request
    category_type = request.GET.get('category_type')
    category_id = request.GET.get('category_id')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    search_query = request.GET.get('search')
    items_per_page = int(request.GET.get('items_per_page', 10))

    # Apply filters
    if category_type in ['Income', 'Expense']:  # Use capitalized values
        transactions = transactions.filter(category_type=category_type)
    if category_id:
        try:
            category_id = int(category_id)
            transactions = transactions.filter(category_id=category_id)
        except ValueError:
            pass
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            transactions = transactions.filter(date__gte=start_date)
        except ValueError:
            pass
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            transactions = transactions.filter(date__lte=end_date)
        except ValueError:
            pass
    if search_query:
        transactions = transactions.filter(description__icontains=search_query)

    # Pagination
    paginator = Paginator(transactions, items_per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Summary Calculations
    total_transactions = transactions.count()

    total_income = transactions.aggregate(
        total=Sum(
            Case(
                When(category_type='Income', then='amount'),
                output_field=DecimalField()
            )
        )
    )['total'] or 0

    total_expense = transactions.aggregate(
        total=Sum(
            Case(
                When(category_type='Expense', then='amount'),
                output_field=DecimalField()
            )
        )
    )['total'] or 0

    balance = total_income - total_expense

    context = {
        'transactions': page_obj,
        'total_transactions': total_transactions,
        'total_income': total_income,
        'total_expense': total_expense,
        'balance': balance,
        'category_type': category_type,
        'category_id': category_id,
        'start_date': start_date,
        'end_date': end_date,
        'search_query': search_query,
        'items_per_page': items_per_page,
    }

    return render(request, 'admin_dashboard/transaction_management.html', context)


@login_required
def payment_management(request):
    today = date.today()

    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    payments = Payment.objects.order_by('-created_at')  # Fetch all payments

    # Apply filters
    if search_query:
        payments = payments.filter(razorpay_order_id__icontains=search_query)
    if status_filter:
        payments = payments.filter(status=status_filter)

    # Pagination
    paginator = Paginator(payments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Revenue Metrics
    total_revenue = payments.filter(status="Completed").aggregate(total_amount=Sum('amount'))['total_amount'] or 0
    month = int(request.GET.get('month', today.month))  # Default to current month if not provided
    year = int(request.GET.get('year', today.year))  # Default to current year if not provided
    monthly_revenue = payments.filter(
        status="Completed",
        created_at__month=month,
        created_at__year=year
    ).aggregate(total_monthly=Sum('amount'))['total_monthly'] or 0
    failed_payments = payments.filter(status="Failed").count()

    # Revenue Trend for Chart.js (Last 12 months)
    revenue_trend = (
        payments.filter(status="Completed")
        .annotate(month=TruncMonth('created_at'))
        .values("month")
        .annotate(revenue=Sum("amount"))
        .order_by("month")
    )

    months = [entry["month"].strftime("%Y-%m") for entry in revenue_trend]
    revenue_data = [float(entry["revenue"]) for entry in revenue_trend]

    context = {
        "payments": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        'today': today,

        "total_revenue": total_revenue,
        "monthly_revenue": monthly_revenue,
        "failed_payments": failed_payments,
        "months": mark_safe(json.dumps(months)),  # JSON-safe for Chart.js
        "revenue_data": mark_safe(json.dumps(revenue_data)),  # JSON-safe for Chart.js
    }

    return render(request, 'admin_dashboard/payment_management.html', context)

@login_required
def export_payments(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="payments.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Payment ID", "User", "Razorpay Order ID", "Razorpay Payment ID",
        "Razorpay Signature", "Amount", "Status", "Date"
    ])

    payments = Payment.objects.all().order_by('-created_at')  # Fetch all payments sorted by latest

    for payment in payments:
        writer.writerow([
            payment.payment_id,  # Use UUID as payment ID
            payment.user.username,  # Fetch the username of the user
            payment.razorpay_order_id,
            payment.razorpay_payment_id if payment.razorpay_payment_id else "N/A",
            payment.razorpay_signature if payment.razorpay_signature else "N/A",
            payment.amount,
            payment.status,  # Use the raw status
            payment.created_at.strftime("%Y-%m-%d %H:%M:%S")  # Format the date
        ])

    return response


@login_required
def notification_management(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            recipient_id = data.get('recipient')
            title = data.get('title')
            message = data.get('message')

            if not title or not message:
                return JsonResponse({'error': 'All fields are required'}, status=400)

            if recipient_id == 'all':
                users = User.objects.all()
                for user in users:
                    Notification.objects.create(
                        user=user,
                        title=title,
                        message=message,
                        status='sent',
                        timestamp=now()
                    )
            else:
                user = User.objects.get(id=recipient_id)
                Notification.objects.create(
                    user=user,
                    title=title,
                    message=message,
                    status='sent',
                    timestamp=now()
                )

            return JsonResponse({'message': 'Notification sent successfully'})

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except User.DoesNotExist:
            return JsonResponse({'error': 'User does not exist'}, status=400)

    users = User.objects.all()
    notifications = Notification.objects.all().order_by('-timestamp')
    print(users)  # Debugging statement
    print(notifications)  # Debugging statement
    return render(request, 'admin_dashboard/notification_management.html', {'users': users, 'notifications': notifications})

@login_required
def settings_view(request):
    settings = AdminSettings.objects.first()

    if request.method == "POST":
        site_name = request.POST.get("site_name")
        site_description = request.POST.get("site_description")
        admin_name = request.POST.get("admin_name")
        admin_email = request.POST.get("admin_email")
        admin_phone = request.POST.get("admin_phone")
        admin_avatar = request.FILES.get("admin_avatar")

        if settings:
            settings.site_name = site_name
            settings.site_description = site_description
            settings.admin_name = admin_name
            settings.admin_email = admin_email
            settings.admin_phone = admin_phone

            if admin_avatar:
                settings.admin_avatar = admin_avatar
            
            settings.save()
        else:
            AdminSettings.objects.create(
                site_name=site_name,
                site_description=site_description,
                admin_name=admin_name,
                admin_email=admin_email,
                admin_phone=admin_phone,
                admin_avatar=admin_avatar
            )

        return redirect("settings")

    return render(request, "admin_dashboard/settings.html", {"settings": settings})




def user_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)

            # Redirect based on role
            if user.is_superuser:  # Admin user
                return redirect('admin_dashboard')
            else:  # Regular user
                return redirect('user_dashboard')
        else:
            messages.error(request, "Invalid email or password!")

    return render(request, "admin_dashboard/login.html")

# Duplicate admin_dashboard function removed

@login_required
def user_dashboard(request):
    return render(request, "user_dashboard/index.html")

@login_required
def admin_logout(request):
    logout(request)
    messages.info(request, 'Logged out successfully.')
    return redirect('user_login')


def user_signup(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        phone_no = request.POST.get("phone_no")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        # Check if passwords match
        if password != confirm_password:
            messages.error(request, "Passwords do not match!")
            return redirect("user_signup")

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered!")
            return redirect("user_signup")

        # Create user
        user = User.objects.create_user(username=username, email=email, phone_no=phone_no, password=password)
        user.save()

        messages.success(request, "Signup successful! You can now log in.")
        return redirect("user_login")  # Redirect to login page after signup

    return render(request, "admin_dashboard/signup.html")
