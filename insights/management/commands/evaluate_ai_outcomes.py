"""
Management Command: evaluate_ai_outcomes
=========================================
Usage:
    python manage.py evaluate_ai_outcomes

What it does:
    Loops through all AIInsightsLog entries that are still 'pending'
    AND were created at least 30 days ago.

    For each log it:
    1. Pulls the CURRENT month's spending for that category from the DB.
    2. Compares against the `spend_at_advice` figure stored in context_snapshot.
    3. Labels the outcome:
        - improved  → spend dropped by > 5%
        - worsened  → spend rose by   > 5%
        - neutral   → within ±5% band
    4. Fills in `outcome_snapshot` and `evaluated_at` and saves.

    After all evaluations, automatically fires the export command
    to refresh ai_training_feedback.csv.
"""

import logging
from datetime import timedelta, datetime

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum

from insights.models import AIInsightsLog
from transactions.models import Transaction

logger = logging.getLogger(__name__)

IMPROVEMENT_THRESHOLD = 0.05   # 5% swing = meaningful change


class Command(BaseCommand):
    help = "Evaluate AI insight outcomes by comparing advice-time vs current spending."

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("🔍  Evaluating AI Insight Outcomes..."))

        cutoff = timezone.now() - timedelta(days=30)
        pending_logs = AIInsightsLog.objects.filter(
            outcome_label="pending",
            created_at__lte=cutoff,
        ).select_related("user")

        if not pending_logs.exists():
            self.stdout.write(self.style.WARNING(
                "⚠️  No pending logs older than 30 days found. Nothing to evaluate."
            ))
            return

        evaluated = 0
        for log in pending_logs:
            ctx = log.context_snapshot or {}
            spend_at_advice = ctx.get("current_month_spending", 0.0)

            # Determine category from feature_name
            category = ""
            if ":" in log.feature_name:
                category = log.feature_name.split(":", 1)[-1].strip()

            # Skip monthly-review logs — they have no single category spending
            if not category:
                continue

            # Pull current month spending for this user+category
            today = datetime.today()
            current_spend = float(
                Transaction.objects.filter(
                    user=log.user,
                    category_type="expense",
                    date__year=today.year,
                    date__month=today.month,
                ).filter(
                    category__name=category,
                ).aggregate(total=Sum("amount"))["total"] or 0.0
            )

            # Compute pct change
            if spend_at_advice > 0:
                pct_change = (current_spend - spend_at_advice) / spend_at_advice
            else:
                pct_change = 0.0

            if pct_change < -IMPROVEMENT_THRESHOLD:
                label = "improved"
            elif pct_change > IMPROVEMENT_THRESHOLD:
                label = "worsened"
            else:
                label = "neutral"

            log.outcome_snapshot = {
                "spend_after": round(current_spend, 2),
                "pct_change_vs_advice": round(pct_change * 100, 2),
                "evaluated_month": today.strftime("%Y-%m"),
            }
            log.outcome_label = label
            log.evaluated_at = timezone.now()
            log.save(update_fields=["outcome_snapshot", "outcome_label", "evaluated_at"])
            evaluated += 1

            self.stdout.write(
                f"    [{label.upper():8s}] {log.user.username:<15} | {category:<20} | "
                f"advice: ₹{spend_at_advice:>8.0f} → now: ₹{current_spend:>8.0f} ({pct_change*100:+.1f}%)"
            )

        self.stdout.write(self.style.SUCCESS(f"\n✅  Evaluated {evaluated} logs."))

        # Auto-refresh training CSV after evaluation
        self.stdout.write(self.style.HTTP_INFO("⚙️  Refreshing training CSV..."))
        from django.core.management import call_command
        call_command("export_ai_training_data", all=True)
