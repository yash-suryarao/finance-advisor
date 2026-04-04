"""
    Every time a new AIInsightsLog row is saved:
    - Fire the export_ai_training_data management command in a
      background thread so the training CSV stays fresh WITHOUT
      blocking the HTTP response.

    The export is skipped if no evaluated (non-pending) records
    exist yet, keeping the CSV clean.
"""

import logging
import threading

from django.db.models.signals import post_save
from django.dispatch import receiver

from insights.models import AIInsightsLog

logger = logging.getLogger(__name__)


def _run_export():
    """Runs in a daemon thread — fires the management command without blocking the web request."""
    try:
        from django.core.management import call_command
        call_command("export_ai_training_data", all=True, verbosity=0)
        logger.info("[AIInsightsLog signal] Training CSV refreshed.")
    except Exception as e:
        logger.error(f"[AIInsightsLog signal] Export failed: {e}")


@receiver(post_save, sender=AIInsightsLog)
def on_ai_insight_saved(sender, instance, created, **kwargs):
    """
    Triggers a non-blocking background CSV export every time a new
    AI insight is logged, keeping the feedback dataset up-to-date.
    """
    if created:
        t = threading.Thread(target=_run_export, daemon=True)
        t.start()
        logger.debug(f"[Signal] AIInsightsLog #{instance.pk} saved — export queued.")
