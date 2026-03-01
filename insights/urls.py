from django.urls import path

from .views import ai_insights
from .views import accept_suggested_budget,BudgetInsightView
from .views import get_notifications, mark_notifications_read


urlpatterns = [
    path('ai-insights/', ai_insights, name='ai-insights'),
    path('accept-suggested-budget/', accept_suggested_budget, name='accept-suggested-budget'),
    path('budget-insights/', BudgetInsightView.as_view(), name='budget-insights'),
    path('notifications/', get_notifications, name='get_notifications'),
    path('mark-notifications-read/', mark_notifications_read, name='mark_notifications_read'),

]

