# transactions/signals.py
import threading
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Transaction
from .utils import check_budget_alert, export_all_transactions_to_csv

# Global variables for debouncing
_export_timer = None
_EXPORT_COOLDOWN_SECONDS = 15.0

def _trigger_export():
    try:
        export_all_transactions_to_csv()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to export consolidated CSV: {e}")

def schedule_csv_export():
    """
    Schedules an asynchronous export of all transactions to a CSV file.
    Uses a 15-second debounce so rapid successive saves don't overload the server.
    """
    global _export_timer
    
    if _export_timer is not None:
        _export_timer.cancel()
        
    _export_timer = threading.Timer(_EXPORT_COOLDOWN_SECONDS, _trigger_export)
    _export_timer.start()


@receiver(post_save, sender=Transaction)
def transaction_saved(sender, instance, created, **kwargs):
    if created and instance.category_type == 'expense':
        check_budget_alert(instance.user)
    
    # Schedule debounced global CSV export
    schedule_csv_export()

@receiver(post_delete, sender=Transaction)
def transaction_deleted(sender, instance, **kwargs):
    # Schedule debounced global CSV export
    schedule_csv_export()
