"""
BACKEND MODULE - ROOT URLS (backend/urls.py)
--------------------------------------------
This is the master URL routing file for the entire Django project.
It defines all top-level URL paths and delegates them to their respective app `urls.py` files.
It is organized into three main sections:
1. JWT Authentication Routes (Login/Refresh)
2. Core API Routes (Transactions, Payments, Insights via DRF)
3. App / Frontend Routes (HTML Views via Django Templates)
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static

from frontend.views import (
    dashboard_stats, login_view, signup_view, dashboard_page,
    transactions_page, analysis_page, profile_page
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # ==========================================
    # 1. JWT Authentication Routes
    # ==========================================
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # Login
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # Refresh token

    # ==========================================
    # 2. Core API Routes
    # ==========================================
    path('api/transactions/', include('transactions.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/insights/', include('insights.urls')),
    
    # ==========================================
    # 3. App / Frontend HTML Routes
    # ==========================================
    path('users/', include('users.urls')),
    path('admin_dashboard/', include('admin_dashboard.urls')),
    path('frontend/', include('frontend.urls')),
    path('dashboard/', dashboard_page, name='dashboard_page'),
    path('transactions/', transactions_page, name='transactions_page'),

    path('analysis/', analysis_page, name='analysis_page'),
    path('profile/', profile_page, name='profile_page'),
    path('dashboard-stats/', dashboard_stats, name='dashboard_stats'),
    
    # Redirect root to a default view (e.g. frontend dashboard_stats if authenticated)
    path('', login_view, name='home'),
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

