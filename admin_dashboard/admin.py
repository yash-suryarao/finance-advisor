from django.contrib import admin

# Unregister SolarSchedule from celery-beat admin.
# This table has been dropped from the DB — it's irrelevant for a finance app.
# Interval, Crontab, and PeriodicTask are kept for future notifications.
try:
    from django_celery_beat.admin import SolarScheduleAdmin
    from django_celery_beat.models import SolarSchedule
    admin.site.unregister(SolarSchedule)
except Exception:
    pass  # Silently ignore if already unregistered or model unavailable
