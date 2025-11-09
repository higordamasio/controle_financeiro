from django.contrib import admin
from django.urls import path

from core.views import (
    dashboard, new_transaction,
    receipts_view, expenses_view, add_section,
    edit_transaction, delete_transaction, toggle_status,
    transactions_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard, name="dashboard"),
    path("transacoes/nova/", new_transaction, name="new_transaction"),
    path("transacoes/<int:pk>/editar/", edit_transaction, name="edit_transaction"),
    path("transacoes/<int:pk>/excluir/", delete_transaction, name="delete_transaction"),
    path("transacoes/<int:pk>/toggle/", toggle_status, name="toggle_status"),
    path("receitas/", receipts_view, name="receipts"),
    path("despesas/", expenses_view, name="expenses"),
    path("secao/add/", add_section, name="add_section"),
    path("transacoes/", transactions_view, name="transactions"),
]
