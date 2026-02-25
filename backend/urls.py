"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static

from frontend.views import (
    dashboard_stats, login_view, signup_view, dashboard_page,
    transactions_page, budget_page, saving_goals_page,
    recurring_payments_page, group_expenses_page, analysis_page, profile_page
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # JWT Authentication Routes
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),  # Login
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),  # Refresh token

    # Core App Routes
    path('api/group-expenses/', include('group_expenses.urls')),
    path('api/transactions/', include('transactions.urls')),
    path('api/payments/', include('payments.urls')),
    path('api/insights/', include('insights.urls')),
    
    # App Routes (Without API prefix for views or distinct patterns)
    path('users/', include('users.urls')),
    path('admin_dashboard/', include('admin_dashboard.urls')),
    path('frontend/', include('frontend.urls')),
    path('dashboard/', dashboard_page, name='dashboard_page'),
    path('transactions/', transactions_page, name='transactions_page'),
    path('budget/', budget_page, name='budget_page'),
    path('saving-goals/', saving_goals_page, name='saving_goals_page'),
    path('recurring-payments/', recurring_payments_page, name='recurring_payments_page'),
    path('group-expenses/', group_expenses_page, name='group_expenses_page'),
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

