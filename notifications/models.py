"""
NOTIFICATIONS MODULE - MODELS (notifications/models.py)
-------------------------------------------------------
Defines the database schema for the system-wide notification infrastructure.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.utils.timezone import now

User = get_user_model()

# ==========================================
# 1. NOTIFICATION SYSTEM MODEL
# Stores global or user-targeted alerts, messages, and their read status.
# ==========================================

class Notification(models.Model):
    RECIPIENT_CHOICES = [
        ('all', 'All Users'),
    ]

    recipients = models.CharField(max_length=10, choices=RECIPIENT_CHOICES,default="")
    title = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=10, default='sent')
    timestamp = models.DateTimeField(default=now)

    def __str__(self):
        return self.title

