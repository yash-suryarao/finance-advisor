"""
ANALYTICS MODULE - VIEWS (analytics/views.py)
---------------------------------------------
This file contains the administrative API endpoints for platform-wide metrics.
It allows admins to fetch total user counts, global revenues, and recent activity logs.
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from django.utils.timezone import now
from django.db.models import Sum, Count
from datetime import timedelta
from transactions.models import Transaction
from django.contrib.auth import get_user_model
from .serializers import UserCountSerializer, RevenueSerializer
from payments.models import Subscription



User = get_user_model()
permission_classes = [IsAdminUser]

# ==========================================
# 1. ADMIN USER STATISTICS
# Endpoints to fetch active/total user counts for the admin dashboard.
# ==========================================

@api_view(['GET'])
def user_statistics(request):
    total_users = User.objects.count()

    data = {
        "total_users": total_users,
    }
    serializer = UserCountSerializer(data)
    return Response(serializer.data)

# ==========================================
# 2. ADMIN REVENUE STATISTICS
# Endpoints to compute platform-wide total and monthly revenues.
# ==========================================

@api_view(['GET'])
def revenue_statistics(request):
    total_revenue = Transaction.objects.aggregate(Sum('amount'))['amount__sum'] or 0
    current_month = now().month
    monthly_revenue = Transaction.objects.filter(
        created_at__month=current_month
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    data = {
        "total_revenue": total_revenue,
        "monthly_revenue": monthly_revenue,
    }
    serializer = RevenueSerializer(data)
    return Response(serializer.data)

# ==========================================
# 3. ADMIN ACTIVITY LOGS
# Endpoints to fetch a stream of recent user activities across the platform.
# ==========================================

@api_view(['GET'])
def activity_logs(request):
    logs = ActivityLog.objects.all().order_by('-timestamp')[:50]
    serializer = ActivityLogSerializer(logs, many=True)
    return Response(serializer.data)
