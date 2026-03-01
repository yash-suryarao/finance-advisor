from django.urls import path

from .views import ai_insights
from .views import accept_suggested_budget,BudgetInsightView
from .views import get_notifications, mark_notifications_read
from .views import add_savings_goal, get_savings_progress


urlpatterns = [
    path('ai-insights/', ai_insights, name='ai-insights'),
    path('accept-suggested-budget/', accept_suggested_budget, name='accept-suggested-budget'),
    path('budget-insights/', BudgetInsightView.as_view(), name='budget-insights'),
    path('notifications/', get_notifications, name='get_notifications'),
    path('mark-notifications-read/', mark_notifications_read, name='mark_notifications_read'),
    path('add-goal/', add_savings_goal, name='add_savings_goal'),
    path('goal-progress/', get_savings_progress, name='get_savings_progress'),
]

