from django.contrib import admin
from django.contrib.auth.models import Group

# ── Hide "Groups" from the admin panel ──────────────────────────────────────
# auth_group stays in the DB (Django requires it), but this app uses no
# group-based permissions so the menu entry is removed for a cleaner admin.
try:
    admin.site.unregister(Group)
except Exception:
    pass  # Already unregistered or not registered

# ── Hide SolarSchedule from celery-beat admin ────────────────────────────────
# Table dropped from DB — sunrise/sunset scheduling is irrelevant for a finance app.
# Interval, Crontab, and PeriodicTask are kept for future notification scheduling.
try:
    from django_celery_beat.models import SolarSchedule
    admin.site.unregister(SolarSchedule)
except Exception:
    pass
