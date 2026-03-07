from django.urls import path
from . import views

urlpatterns = [
    # ==========================================
    # 1. DASHBOARD OVERVIEW
    # ==========================================
    path('', views.admin_dashboard, name='admin_dashboard'),

    # ==========================================
    # 2. USER MANAGEMENT
    # ==========================================
    path('users/', views.user_management, name='user_management'),
    path('users/export/', views.export_users, name='export_users'),

    # ==========================================
    # 3. TRANSACTIONS & PAYMENTS
    # ==========================================
    path('transactions/', views.transaction_management, name='transaction_management'),
    path('payments/', views.payment_management, name='payment_management'),
    path('payments/export/', views.export_payments, name='export_payments'),

    # ==========================================
    # 4. NOTIFICATIONS
    # ==========================================
    path('notifications/', views.notification_management, name='notification_management'),

    # ==========================================
    # 5. ADMIN SETTINGS
    # ==========================================
    path('settings/', views.settings_view, name='settings'),

    # ==========================================
    # 6. ADMIN AUTHENTICATION
    # ==========================================
    path('login/', views.user_login, name='user_login'),
    path('signup/', views.user_signup, name='user_signup'),
    path('logout/', views.admin_logout, name='admin_logout'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
]