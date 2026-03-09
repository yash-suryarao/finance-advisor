from django.urls import path
from .views import (
    dashboard_stats, financial_summary, spending_analysis, login_view, signup_view, analysis_page
)

urlpatterns = [
    # ==========================================
    # 1. PAGE ROUTES
    # ==========================================
    path('login/', login_view, name='login'),
    path('signup/', signup_view, name='signup'),
    path('analysis/', analysis_page, name='analysis_page'),

    # ==========================================
    # 2. DATA APIs
    # ==========================================
    path('dashboard-stats/', dashboard_stats, name='dashboard_stats'),
    path('financial-summary/', financial_summary, name='financial_summary'),
    path('spending-analysis/', spending_analysis, name='spending_analysis'),
]
