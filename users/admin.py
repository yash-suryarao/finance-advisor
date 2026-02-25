from django.contrib import admin
from .models import User, Profile, FinancialData

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['id', 'email', 'username', 'full_name', 'phone_no', 'role', 'last_login', 'date_joined']
    search_fields = ['email', 'username', 'full_name']
    list_filter = ['role', 'date_joined', 'last_login']

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'occupation', 'annual_income', 'subscription_plan']

@admin.register(FinancialData)
class FinancialDataAdmin(admin.ModelAdmin):
    list_display = ['user', 'monthly_income_salary', 'total_debt']
