"""
1. Reads ALL AIInsightsLog entries (context_snapshot + outcome fields)
2. Merges with corresponding transaction history per user+category
3. Exports an enriched CSV to media/datasets/ai_training_feedback.csv

This file is the labeled dataset that ML models will consume for
continuous self-improvement (Phase D of the feedback loop).

Columns in output CSV:
    user_id, feature_name, category, advice_date,
    spend_at_advice, spend_after,
    pct_change, anomaly_flag, forecast_at_advice,
    outcome_label, generated_insight_snippet
"""

import csv
import os
import json
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from insights.models import AIInsightsLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Export enriched AIInsightsLog data to a training CSV for ML model feedback loop."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Export all records regardless of outcome_label (default: only evaluated records).",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO("⚙️  Starting AI Training Data Export..."))

        export_all = options.get("all", False)

        qs = AIInsightsLog.objects.select_related("user").all()
        if not export_all:
            # By default only export logs that have been evaluated (not 'pending')
            qs = qs.exclude(outcome_label="pending")

        if not qs.exists():
            self.stdout.write(self.style.WARNING(
                "⚠️  No evaluated AI insight logs found. "
                "Run 'python manage.py evaluate_ai_outcomes' first, or pass --all to include pending records."
            ))
            return

        out_dir = os.path.join(settings.BASE_DIR, "media", "datasets")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "ai_training_feedback.csv")

        rows_written = 0
        fieldnames = [
            "user_id",
            "feature_name",
            "category",
            "advice_date",
            "spend_at_advice",
            "prev_month_spend_at_advice",
            "pct_change_at_advice",
            "anomaly_flag",
            "forecast_at_advice",
            "budget_reduction_advised",
            "spend_after",
            "outcome_label",
            "evaluated_at",
            "insight_snippet",
        ]

        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for log in qs:
                ctx = log.context_snapshot or {}
                out_ctx = log.outcome_snapshot or {}

                # Extract category from feature_name, e.g. "Category Insight: Food" → "Food"
                category = ""
                if ":" in log.feature_name:
                    category = log.feature_name.split(":", 1)[-1].strip()

                row = {
                    "user_id":                   log.user_id,
                    "feature_name":              log.feature_name,
                    "category":                  category,
                    "advice_date":               log.created_at.strftime("%Y-%m-%d"),
                    "spend_at_advice":           ctx.get("current_month_spending", ""),
                    "prev_month_spend_at_advice":ctx.get("previous_month_spending", ""),
                    "pct_change_at_advice":      ctx.get("percentage_change", ""),
                    "anomaly_flag":              ctx.get("anomaly_flag", ""),
                    "forecast_at_advice":        ctx.get("forecasted_next_month_spending", ""),
                    "budget_reduction_advised":  ctx.get("recommended_budget_limit", ""),
                    "spend_after":               out_ctx.get("spend_after", ""),
                    "outcome_label":             log.outcome_label,
                    "evaluated_at":              log.evaluated_at.strftime("%Y-%m-%d") if log.evaluated_at else "",
                    "insight_snippet":           log.generated_insight[:120].replace("\n", " "),
                }
                writer.writerow(row)
                rows_written += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅  Exported {rows_written} records → {out_path}"
        ))
