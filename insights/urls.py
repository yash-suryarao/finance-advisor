from django.urls import path

from .views import ai_insights, category_insight_detail
from .views import accept_suggested_budget,BudgetInsightView
from .views import get_notifications, mark_notifications_read
from .views import add_savings_goal, get_savings_progress
from .views import delete_savings_goal, update_goal_savings, withdraw_goal_savings
from . import views

urlpatterns = [
    # ==========================================
    # 1. AI & FORECASTING
    # ==========================================
    path('ai-insights/', ai_insights, name='ai-insights'),
    path('category-detail/', category_insight_detail, name='category-insight-detail'),
    path('budget-insights/', BudgetInsightView.as_view(), name='budget-insights'),
    path('monthly-review/', views.monthly_xai_review, name='monthly-review'),
    path('anomaly-heatmap/', views.get_anomaly_heatmap, name='anomaly-heatmap'),
    path('wellness-analyzer/', views.wellness_analyzer, name='wellness-analyzer'),
    path('category-burn-rate/', views.category_burn_rate, name='category-burn-rate'),
    path('peer-benchmarking/', views.peer_benchmarking, name='peer-benchmarking'),

    # Analysis Page — Real Data Endpoints
    path('analysis-summary/', views.get_analysis_summary, name='analysis-summary'),
    path('spending-trends/', views.get_spending_trends, name='spending-trends'),
    path('budget-trajectory/', views.get_budget_trajectory, name='budget-trajectory'),

    # AI Budget Advisory Features
    path('ai-budget-suggestions/', views.ai_budget_suggestions, name='ai-budget-suggestions'),
    path('ai-budget-planner/', views.ai_budget_planner, name='ai-budget-planner'),
    path('overspend-predictions/', views.overspend_predictions, name='overspend-predictions'),
    path('accept-suggested-budget/', views.accept_suggested_budget, name='accept-suggested-budget'),
    path('log-ai-action/', views.log_ai_action, name='log-ai-action'),



    # ==========================================
    # 3. NOTIFICATIONS & 4. SAVINGS GOALS
    # ==========================================
    path('notifications/', get_notifications, name='get_notifications'),
    path('mark-notifications-read/', mark_notifications_read, name='mark_notifications_read'),
    path('add-goal/', add_savings_goal, name='add_savings_goal'),
    path('goal-progress/', get_savings_progress, name='get_savings_progress'),
    path('delete-goal/<int:goal_id>/', delete_savings_goal, name='delete_savings_goal'),
    path('update-goal-savings/', update_goal_savings, name='update_goal_savings'),
    path('withdraw-goal-savings/', withdraw_goal_savings, name='withdraw_goal_savings'),
    path('savings-projections/', views.get_savings_projections, name='savings_projections'),
]
