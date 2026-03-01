# transactions/admin.py
from django.contrib import admin
from .models import Transaction, Category, Budget

# Registering the Transaction model
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'category', 'date', 'category_type')
    search_fields = ('user__username', 'category')
    list_filter = ('category_type', 'date')


# Registering the Category model
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'user')
    search_fields = ('name', 'user__username')


# Registering the Budget model
@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('user', 'category', 'monthly_limit', 'created_at')
    search_fields = ('user__username', 'category__name')

from .models import DeletedTransaction


# Registering the DeletedTransaction model
@admin.register(DeletedTransaction)
class DeletedTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'category_name', 'deleted_at')
    search_fields = ('user__username', 'category_name')
    list_filter = ('category_type', 'deleted_at')
