from django.contrib import admin
from .models import SavingsGoal, AIInsightsLog

@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'user', 'goal_name', 'target_amount', 'saved_amount', 'deadline', 'status')
    list_filter = ('status', 'deadline')
    search_fields = ('goal_name', 'user__username', 'user_id', 'status', 'deadline')


@admin.register(AIInsightsLog)
class AIInsightsLogAdmin(admin.ModelAdmin):
    list_display  = ('user', 'feature_name', 'outcome_label', 'created_at', 'evaluated_at', 'insight_preview')
    list_filter   = ('feature_name', 'outcome_label', 'created_at')
    search_fields = ('user__username', 'feature_name')
    readonly_fields = (
        'user', 'feature_name', 'context_snapshot',
        'generated_insight', 'outcome_snapshot',
        'outcome_label', 'created_at', 'evaluated_at',
    )

    @admin.display(description='Insight Preview')
    def insight_preview(self, obj):
        return (obj.generated_insight[:100] + '…') if len(obj.generated_insight) > 100 else obj.generated_insight
