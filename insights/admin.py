from django.contrib import admin
from .models import SavingsGoal

@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'goal_name', 'target_amount', 'saved_amount', 'deadline', 'status')
    list_filter = ('status', 'deadline')
    search_fields = ('goal_name', 'user__username')
