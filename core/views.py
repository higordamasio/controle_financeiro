import calendar
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from .models import (
    Transaction,
    Category,
    Account,
    TransactionStatus,  # enum PENDENTE/PAGA
)

from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_DOWN

import uuid
from datetime import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal, ROUND_DOWN


# --------------------------------------------
# Helpers
# --------------------------------------------

def _period_from_request(request):
    """Lê ?year=YYYY&month=MM; padrão = mês atual."""
    today = now().date()
    year = int(request.GET.get("year", today.year))
    month = int(request.GET.get("month", today.month))
    return year, month

MONTHS = list(range(1, 13))

# --------------------------------------------
# Dashboard
# --------------------------------------------

@login_required
def dashboard(request):
    year, month = _period_from_request(request)

    qs = Transaction.objects.filter(
        date__year=year,
        date__month=month,
        account__owner=request.user,
    ).select_related("account", "category")

    totals = qs.values("category__kind").annotate(total=Sum("amount"))
    total_in = sum(t["total"] for t in totals if t["category__kind"] == "IN") or Decimal("0")
    total_ex = sum(t["total"] for t in totals if t["category__kind"] == "EX") or Decimal("0")
    total_ex_abs = abs(total_ex)
    net = total_in + total_ex

    # --- Despesas por categoria (mês/ano) ---
    ex_by_cat_qs = (
        qs.filter(category__kind="EX")
        .values("category__name")
        .annotate(total=Sum("amount"))
    )

    # transforma em lista, pega módulo (positivo) e ordena desc
    ex_by_cat = []
    for r in ex_by_cat_qs:
        if r["total"]:  # só categorias com algum valor
            ex_by_cat.append({
                "name": r["category__name"],
                "total": abs(r["total"] or Decimal("0")),
            })

    ex_by_cat.sort(key=lambda x: x["total"], reverse=True)

    bar_labels = [x["name"] for x in ex_by_cat]
    bar_values = [float(x["total"]) for x in ex_by_cat]

    qs_paid = qs.filter(status=TransactionStatus.PAID)

    totals_paid = qs_paid.values("category__kind").annotate(total=Sum("amount"))
    total_in_paid = sum(t["total"] for t in totals_paid if t["category__kind"] == "IN") or Decimal("0")
    total_ex_paid = sum(t["total"] for t in totals_paid if t["category__kind"] == "EX") or Decimal("0")
    net_paid = total_in_paid + total_ex_paid  # saldo parcial (apenas pagos)

    total_ex_paid_abs = abs(total_ex_paid)

    accounts = Account.objects.filter(owner=request.user)
    account_balances = []
    for acc in accounts:
        acc_sum = acc.transactions.aggregate(s=Sum("amount"))["s"] or Decimal("0")
        account_balances.append({"account": acc, "balance": acc.initial_balance + acc_sum})

    context = {
        "months": MONTHS,
        "month": month,
        "year": year,
        "month_name": calendar.month_name[month],
        "total_in": total_in,
        "total_ex": total_ex,
        "total_ex_abs": total_ex_abs,
        "net": net,

        # >>> NOVOS <<<
        "total_in_paid": total_in_paid,
        "total_ex_paid": total_ex_paid,
        "total_ex_paid_abs": total_ex_paid_abs,
        "net_paid": net_paid,
        # -------------

        "recent": qs.order_by("-date", "-id")[:10],
        "account_balances": account_balances,

        "bar_labels": bar_labels,
        "bar_values": bar_values,
    }
    return render(request, "dashboard.html", context)

# --------------------------------------------
# Nova transação (com presets e sidebar)
# --------------------------------------------

@login_required
def new_transaction(request):
    # presets por querystring (category, account, amount, desc, date, next)
    preset = {
        "date": request.GET.get("date") or "",
        "description": request.GET.get("desc") or "",
        "account_id": request.GET.get("account") or "",
        "category_id": request.GET.get("category") or "",
        "amount": request.GET.get("amount") or "",
        "next": request.GET.get("next") or "",
    }

    if request.method == "POST":
        try:
            acc = Account.objects.get(id=request.POST["account"], owner=request.user)
            cat = Category.objects.get(id=request.POST["category"])

            amt = Decimal(str(request.POST["amount"]))
            if cat.kind == "EX" and amt > 0:
                amt = -amt

            status_val = request.POST.get("status") or TransactionStatus.PENDING
            if status_val not in dict(TransactionStatus.choices):
                status_val = TransactionStatus.PENDING

            # Parcelas
            installments = int(request.POST.get("installments") or 1)
            first_due = (request.POST.get("first_due") or request.POST["date"]).strip()

            # input type=date envia ISO (YYYY-MM-DD)
            start_date = datetime.fromisoformat(first_due).date()

            if installments <= 1:
                Transaction.objects.create(
                    date=start_date,
                    description=request.POST["description"].strip(),
                    account=acc,
                    category=cat,
                    amount=amt,
                    status=status_val,
                    installment_no=None,
                    installment_count=None,
                )
            else:
                total = amt
                n = installments

                base = (total / n).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
                diff = total - (base * n)  # ajusta centavinho nas primeiras parcelas

                group = uuid.uuid4()
                desc_base = request.POST["description"].strip() or cat.name

                for i in range(n):
                    part = base
                    # distribui o centavo que sobrou/faltou
                    if diff != 0:
                        step = Decimal("0.01") if diff > 0 else Decimal("-0.01")
                        part = base + step
                        diff -= step

                    due_date = start_date + relativedelta(months=i)

                    Transaction.objects.create(
                        date=due_date,
                        description=f"{desc_base} ({i+1}/{n})",
                        account=acc,
                        category=cat,
                        amount=part,
                        status=(status_val if i == 0 else TransactionStatus.PENDING),
                        group_id=group,
                        installment_no=i + 1,
                        installment_count=n,
                    )

            messages.success(request, f"Lançamento salvo{'s' if installments>1 else ''}! ✅")
            nxt = request.POST.get("next") or preset["next"]
            return redirect(nxt or reverse("dashboard"))

        except Exception as e:
            messages.error(request, f"Erro ao salvar transação: {e}")


    # categorias mais usadas pelo usuário nos últimos 60 dias (para sidebar)
    cutoff = now().date() - timedelta(days=60)
    recent_qs = (
        Transaction.objects.filter(account__owner=request.user, date__gte=cutoff)
        .values("category__id", "category__name", "category__kind")
        .annotate(qtd=Count("id"))
        .order_by("-qtd")[:6]
    )
    recent_cats = [
        {"id": r["category__id"], "name": r["category__name"], "kind": r["category__kind"]}
        for r in recent_qs
    ]

    ctx = {
        "accounts": Account.objects.filter(owner=request.user),
        "categories": Category.objects.all().order_by("kind", "name"),
        "preset": preset,
        "recent_categories": recent_cats,
        "quick_amounts": [20, 50, 100, 150, 200, 350],
        "status_choices": TransactionStatus.choices,
        "installment_options": [1,2,3,4,5,6,7,8,9,10,11,12,18,24],   # <<< AQUI
    }
    return render(request, "new_transaction.html", ctx)

# --------------------------------------------
# Editar / Excluir / Toggle status
# --------------------------------------------

@login_required
def edit_transaction(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, account__owner=request.user)

    if request.method == "POST":
        try:
            acc = Account.objects.get(id=request.POST["account"], owner=request.user)
            cat = Category.objects.get(id=request.POST["category"])
            amt = Decimal(str(request.POST["amount"]))
            if cat.kind == "EX" and amt > 0:
                amt = -amt

            status_val = request.POST.get("status") or TransactionStatus.PENDING
            if status_val not in dict(TransactionStatus.choices):
                status_val = TransactionStatus.PENDING

            tx.date = request.POST["date"]
            tx.description = request.POST["description"].strip()
            tx.account = acc
            tx.category = cat
            tx.amount = amt
            tx.status = status_val
            tx.save()
            messages.success(request, "Transação atualizada! ✅")
            return redirect(request.POST.get("next") or reverse("dashboard"))
        except Exception as e:
            messages.error(request, f"Erro ao atualizar: {e}")

    ctx = {
        "tx": tx,
        "accounts": Account.objects.filter(owner=request.user),
        "categories": Category.objects.all().order_by("kind", "name"),
        "status_choices": TransactionStatus.choices,
        "next": request.GET.get("next") or request.META.get("HTTP_REFERER") or reverse("dashboard"),
    }
    return render(request, "edit_transaction.html", ctx)

@login_required
@require_POST
def delete_transaction(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, account__owner=request.user)
    tx.delete()
    messages.success(request, "Transação excluída. 🗑️")
    return redirect(request.POST.get("next") or reverse("dashboard"))

@login_required
@require_POST
def toggle_status(request, pk):
    tx = get_object_or_404(Transaction, pk=pk, account__owner=request.user)
    tx.status = (
        TransactionStatus.PAID
        if tx.status == TransactionStatus.PENDING
        else TransactionStatus.PENDING
    )
    tx.save(update_fields=["status"])
    return redirect(request.POST.get("next") or reverse("dashboard"))

# --------------------------------------------
# Receitas / Despesas por seção (categoria)
# --------------------------------------------

@login_required
def receipts_view(request):
    year, month = _period_from_request(request)
    sections = Category.objects.filter(kind="IN").order_by("name")
    tx = Transaction.objects.filter(
        date__year=year, date__month=month, account__owner=request.user
    ).select_related("category", "account")

    # ATENÇÃO: usar 'txs' (e não 'items') para evitar conflito com dict.items no template
    by_cat = {c.id: {"category": c, "txs": [], "total": Decimal("0")} for c in sections}
    for t in tx.filter(category__kind="IN"):
        b = by_cat.get(t.category_id)
        if b:
            b["txs"].append(t)
            b["total"] += t.amount

    context = {
        "page_title": "Receitas",
        "year": year,
        "month": month,
        "months": MONTHS,
        "sections": [by_cat[c.id] for c in sections],
    }
    return render(request, "receitas.html", context)

@login_required
def expenses_view(request):
    year, month = _period_from_request(request)
    sections = Category.objects.filter(kind="EX").order_by("name")
    tx = Transaction.objects.filter(
        date__year=year, date__month=month, account__owner=request.user
    ).select_related("category", "account")

    by_cat = {c.id: {"category": c, "txs": [], "total": Decimal("0")} for c in sections}
    for t in tx.filter(category__kind="EX"):
        b = by_cat.get(t.category_id)
        if b:
            b["txs"].append(t)
            b["total"] += t.amount

    context = {
        "page_title": "Despesas",
        "year": year,
        "month": month,
        "months": MONTHS,
        "sections": [by_cat[c.id] for c in sections],
    }
    return render(request, "despesas.html", context)

# --------------------------------------------
# Criar seção (categoria)
# --------------------------------------------

@login_required
def add_section(request):
    """
    GET /secao/add/?kind=IN&name=Receitas Fixas
    GET /secao/add/?kind=EX&name=Despesas Fixas
    """
    kind = request.GET.get("kind")
    name = (request.GET.get("name") or "").strip()

    if kind not in ("IN", "EX"):
        messages.error(request, "Tipo inválido.")
        return redirect("dashboard")
    if not name:
        messages.error(request, "Informe um nome para a seção.")
        return redirect("receipts" if kind == "IN" else "expenses")

    Category.objects.get_or_create(name=name, kind=kind)
    messages.success(request, "Seção criada com sucesso!")
    return redirect("receipts" if kind == "IN" else "expenses")
