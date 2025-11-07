from django.contrib import admin
from .models import Account, Category, Transaction

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "initial_balance")
    search_fields = ("name", "owner__username")

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "kind")
    list_filter = ("kind",)
    search_fields = ("name",)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("date", "description", "account", "category", "amount", "status", "is_fixed")
    list_filter = ("account", "category", "date", "status", "is_fixed")
    search_fields = ("description",)
    date_hierarchy = "date"
