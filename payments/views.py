from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Payment
from django.contrib.auth.models import User
from rest_framework.decorators import api_view
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions
from celery import shared_task
from django.utils.timezone import now
from notifications.models import Notification




