from django.db import models
from django.conf import settings
from datetime import datetime

# ==========================================
# 1. AI FORECASTING MODELS
# ==========================================

class BudgetInsight(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    category = models.CharField(max_length=100, default="General")
    average_spending = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    forecasted_spending = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    savings_recommendation = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(default=datetime.now)

    def __str__(self):
        return f"{self.user.username} - {self.category} Insights"

class AIInsightsLog(models.Model):
    OUTCOME_CHOICES = [
        ('pending',   'Pending'),    # Not yet evaluated
        ('improved',  'Improved'),   # Spending reduced after advice
        ('worsened',  'Worsened'),   # Spending increased after advice
        ('neutral',   'Neutral'),    # No significant change
    ]

    user              = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    feature_name      = models.CharField(max_length=100)
    context_snapshot  = models.JSONField(blank=True, null=True)   # numbers fed to the AI
    generated_insight = models.TextField()                         # what AI said
    outcome_snapshot  = models.JSONField(blank=True, null=True)   # numbers 30 days later
    outcome_label     = models.CharField(max_length=12, choices=OUTCOME_CHOICES, default='pending')
    created_at        = models.DateTimeField(auto_now_add=True)
    evaluated_at      = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.feature_name} ({self.created_at.strftime('%Y-%m-%d')}) [{self.outcome_label}]"

# ==========================================
# 2. SAVINGS & GOALS MODELS
# ==========================================

class SavingsGoal(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    goal_name = models.CharField(max_length=255)
    target_amount = models.DecimalField(max_digits=10, decimal_places=2)
    saved_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    deadline = models.DateField()
    status = models.CharField(max_length=20, choices=[("In Progress", "In Progress"), ("Completed", "Completed"), ("Withdrawn", "Withdrawn")], default="In Progress")
    created_at = models.DateTimeField(default=datetime.now)

    def __str__(self):
        return f"{self.user.username} - {self.goal_name}"

    def update_progress(self):
        """Updates the status based on savings progress."""
        if self.saved_amount >= self.target_amount:
            self.status = "Completed"
            self.save()
