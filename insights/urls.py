from django.urls import path

from .views import ai_insights, category_insight_detail
from .views import accept_suggested_budget,BudgetInsightView
from .views import get_notifications, mark_notifications_read
from .views import add_savings_goal, get_savings_progress
from .views import delete_savings_goal, update_goal_savings, withdraw_goal_savings


urlpatterns = [
    path('ai-insights/', ai_insights, name='ai-insights'),
    path('category-detail/', category_insight_detail, name='category-insight-detail'),
    path('accept-suggested-budget/', accept_suggested_budget, name='accept-suggested-budget'),
    path('budget-insights/', BudgetInsightView.as_view(), name='budget-insights'),
    path('notifications/', get_notifications, name='get_notifications'),
    path('mark-notifications-read/', mark_notifications_read, name='mark_notifications_read'),
    path('add-goal/', add_savings_goal, name='add_savings_goal'),
    path('goal-progress/', get_savings_progress, name='get_savings_progress'),
    path('delete-goal/<int:goal_id>/', delete_savings_goal, name='delete_savings_goal'),
    path('update-goal-savings/', update_goal_savings, name='update_goal_savings'),
    path('withdraw-goal-savings/', withdraw_goal_savings, name='withdraw_goal_savings'),
]

