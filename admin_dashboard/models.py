from django.conf import settings

from django.db import models

class AdminSettings(models.Model):
    # Site Settings
    site_name = models.CharField(max_length=255)
    site_description = models.TextField(blank=True, null=True)

    # Admin Profile Settings
    admin_name = models.CharField(max_length=255, default="Admin")
    admin_email = models.EmailField(unique=True, default="admin1@gmail.com")
    admin_phone = models.CharField(max_length=15, blank=True, null=True)
    admin_avatar = models.ImageField(upload_to="admin_avatars/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.site_name

