from celery import shared_task
from django.utils.timezone import now
from datetime import timedelta
from payments.models import RecurringPayment
import logging

logger = logging.getLogger(__name__)

@shared_task
def send_bill_reminders():
    """
    Checks for upcoming bills due in the next 3 days and processes reminders.
    """
    today = now().date()
    upcoming_limit = today + timedelta(days=3)
    
    upcoming_payments = RecurringPayment.objects.filter(
        next_payment_date__gte=today,
        next_payment_date__lte=upcoming_limit,
        status="active"
    )
    
    for payment in upcoming_payments:
        # In a real app we'd trigger an email, SMS, or push notification here
        days_left = (payment.next_payment_date - today).days
        logger.info(f"Reminder: User {payment.user.email} has a {payment.name} bill of {payment.amount} due in {days_left} days.")
        
    return f"Processed {upcoming_payments.count()} payment reminders."
