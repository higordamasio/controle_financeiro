import calendar
import uuid
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_DOWN

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.timezone import now
from django.views.decorators.http import require_POST

from dateutil.relativedelta import relativedelta

from .models import (
    Transaction,
    Category,
    Account,
    TransactionStatus,  # enum PENDING/PAG (PENDENTE/PAGA)
)

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

    # 🔹 navegação pelos botões do formulário
    nav = request.GET.get("nav")

    if nav == "prev":
        month -= 1
        if month == 0:
            month = 12
            year -= 1

    elif nav == "next":
        month += 1
        if month == 13:
            month = 1
            year += 1

    qs = (
        Transaction.objects
        .filter(date__year=year, date__month=month, account__owner=request.user)
        .select_related("account", "category")
    )

    # Totais gerais do mês (por tipo via categoria)
    totals = qs.values("category__kind").annotate(total=Sum("amount"))
    total_in = sum(t["total"] for t in totals if t["category__kind"] == "IN") or Decimal("0")
    total_ex = sum(t["total"] for t in totals if t["category__kind"] == "EX") or Decimal("0")
    total_ex_abs = abs(total_ex)
    net = total_in + total_ex

    # --- Despesas por categoria (mês/ano) -> para o gráfico de barras ---
    ex_by_cat_qs = (
        qs.filter(category__kind="EX")
          .values("category__name")
          .annotate(total=Sum("amount"))
    )
    ex_by_cat = []
    for r in ex_by_cat_qs:
        if r["total"]:
            ex_by_cat.append({
                "name": r["category__name"],
                "total": abs(r["total"] or Decimal("0")),
            })
    ex_by_cat.sort(key=lambda x: x["total"], reverse=True)
    bar_labels = [x["name"] for x in ex_by_cat]
    bar_values = [float(x["total"]) for x in ex_by_cat]

    # --- Pagos (PAGO) do mês ---
    qs_paid = qs.filter(status=TransactionStatus.PAID)
    totals_paid = qs_paid.values("category__kind").annotate(total=Sum("amount"))
    total_in_paid = sum(t["total"] for t in totals_paid if t["category__kind"] == "IN") or Decimal("0")
    total_ex_paid = sum(t["total"] for t in totals_paid if t["category__kind"] == "EX") or Decimal("0")
    total_ex_paid_abs = abs(total_ex_paid)
    net_paid = total_in_paid + total_ex_paid  # saldo parcial (apenas pagos)

    # --- Pendentes (PENDENTE) do mês ---
    qs_pending = qs.filter(status=TransactionStatus.PENDING)
    totals_pending = qs_pending.values("category__kind").annotate(total=Sum("amount"))
    total_in_pending = sum(t["total"] for t in totals_pending if t["category__kind"] == "IN") or Decimal("0")
    total_ex_pending = sum(t["total"] for t in totals_pending if t["category__kind"] == "EX") or Decimal("0")
    total_ex_pending_abs = abs(total_ex_pending)

    # Saldos por conta (geral, não filtrado por mês) — como você já tinha
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

        # Totais gerais do mês
        "total_in": total_in,
        "total_ex": total_ex,
        "total_ex_abs": total_ex_abs,
        "net": net,

        # Totais pagos / pendentes (mês)
        "total_in_paid": total_in_paid,
        "total_ex_paid": total_ex_paid,
        "total_ex_paid_abs": total_ex_paid_abs,
        "net_paid": net_paid,
        "total_in_pending": total_in_pending,
        "total_ex_pending": total_ex_pending,
        "total_ex_pending_abs": total_ex_pending_abs,

        # Lista e contas
        "recent": qs.order_by("-updated_at", "-id")[:10],
        "account_balances": account_balances,

        # Dados do gráfico de barras de despesas por categoria
        "ex_by_cat": ex_by_cat,
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
        # preset opcional via query (?fixed=1)
        "is_fixed": request.GET.get("fixed") in ("1", "true", "on"),
    }

    if request.method == "POST":
        try:
            acc = Account.objects.get(id=request.POST["account"], owner=request.user)
            cat = Category.objects.get(id=request.POST["category"])

            amt = Decimal(str(request.POST["amount"]))
            # Se for despesa e o valor veio positivo, torna negativo
            if cat.kind == "EX" and amt > 0:
                amt = -amt

            status_val = request.POST.get("status") or TransactionStatus.PENDING
            if status_val not in dict(TransactionStatus.choices):
                status_val = TransactionStatus.PENDING

            # Parcelas
            installments = int(request.POST.get("installments") or 1)
            first_due = (request.POST.get("first_due") or request.POST["date"]).strip()
            start_date = datetime.fromisoformat(first_due).date()  # input type=date (YYYY-MM-DD)

            # Checkbox (só vale quando NÃO parcelado)
            is_fixed_flag = ('is_fixed' in request.POST) and (installments <= 1)

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
                    is_fixed=is_fixed_flag,
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
                        is_fixed=False,  # parcelas nunca são "fixas"
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
        "installment_options": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 18, 24],
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

            # Amount: trata vazio/virgula e entradas inválidas
            raw_amount = (request.POST.get("amount") or "").replace(",", ".").strip()
            try:
                amt = Decimal(raw_amount)
            except (InvalidOperation, ValueError):
                messages.error(request, "Valor inválido. Use número com ponto ou vírgula.")
                return redirect(request.POST.get("next") or reverse("dashboard"))

            # Se for despesa e o valor veio positivo, torna negativo
            if cat.kind == "EX" and amt > 0:
                amt = -amt

            status_val = request.POST.get("status") or TransactionStatus.PENDING
            if status_val not in dict(TransactionStatus.choices):
                status_val = TransactionStatus.PENDING

            tx.date = request.POST["date"]  # YYYY-MM-DD (ok para DateField)
            tx.description = request.POST["description"].strip()
            tx.account = acc
            tx.category = cat
            tx.amount = amt
            tx.status = status_val

            # >>> CORREÇÃO AQUI: identificar parcelamento sem usar group_id <<<
            # - Parcelado se tiver installment_count > 1 OU installment_no definido.
            is_parceled = (tx.installment_count or 0) > 1 or (tx.installment_no is not None)
            if is_parceled:
                tx.is_fixed = False
            else:
                tx.is_fixed = ('is_fixed' in request.POST)

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

    # ← navegação por mês (setinhas)
    nav = request.GET.get("nav")
    if nav == "prev":
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    elif nav == "next":
        month += 1
        if month == 13:
            month = 1
            year += 1

    sections = Category.objects.filter(kind="IN").order_by("name")
    tx = (
        Transaction.objects
        .filter(date__year=year, date__month=month, account__owner=request.user)
        .select_related("category", "account")
    )

    # usar 'txs' (não 'items') no template
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

    # ← navegação por mês (setinhas)
    nav = request.GET.get("nav")
    if nav == "prev":
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    elif nav == "next":
        month += 1
        if month == 13:
            month = 1
            year += 1

    sections = Category.objects.filter(kind="EX").order_by("name")
    tx = (
        Transaction.objects
        .filter(date__year=year, date__month=month, account__owner=request.user)
        .select_related("category", "account")
    )

    by_cat = {
        c.id: {
            "category": c,
            "txs": [],
            "total": Decimal("0"),
            "all_paid": False,
        }
        for c in sections
    }
    for t in tx.filter(category__kind="EX"):
        b = by_cat.get(t.category_id)
        if b:
            b["txs"].append(t)
            b["total"] += t.amount

    for section in by_cat.values():
        section["all_paid"] = bool(section["txs"]) and all(
            t.status == TransactionStatus.PAID for t in section["txs"]
        )

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


@login_required
def transactions_view(request):
    year, month = _period_from_request(request)
    q = (request.GET.get("q") or "").strip()
    selected_status = request.GET.get("status") or ""
    selected_account = None
    try:
        selected_account = int(request.GET.get("account")) if request.GET.get("account") else None
    except ValueError:
        selected_account = None

    qs = (
        Transaction.objects
        .filter(date__year=year, date__month=month, account__owner=request.user)
        .select_related("account", "category")
        .order_by("-date", "-id")
    )

    if selected_account:
        qs = qs.filter(account_id=selected_account)
    if selected_status in dict(TransactionStatus.choices):
        qs = qs.filter(status=selected_status)
    if q:
        qs = qs.filter(description__icontains=q)

    # Totais para os cards
    totals = qs.values("category__kind").annotate(total=Sum("amount"))
    total_in = sum(t["total"] for t in totals if t["category__kind"] == "IN") or Decimal("0")
    total_ex = sum(t["total"] for t in totals if t["category__kind"] == "EX") or Decimal("0")
    total_ex_abs = abs(total_ex)
    net = total_in + total_ex

    qs_paid = qs.filter(status=TransactionStatus.PAID)
    totals_paid = qs_paid.values("category__kind").annotate(total=Sum("amount"))
    total_in_paid = sum(t["total"] for t in totals_paid if t["category__kind"] == "IN") or Decimal("0")
    total_ex_paid = sum(t["total"] for t in totals_paid if t["category__kind"] == "EX") or Decimal("0")
    total_ex_paid_abs = abs(total_ex_paid)
    net_paid = total_in_paid + total_ex_paid

    context = {
        "months": MONTHS,
        "month": month,
        "year": year,
        "accounts": Account.objects.filter(owner=request.user),
        "status_choices": TransactionStatus.choices,
        "selected_account": selected_account,
        "selected_status": selected_status,
        "q": q,

        "txs": qs,
        "tx_count": qs.count(),

        "total_in": total_in,
        "total_ex_abs": total_ex_abs,
        "net": net,
        "total_in_paid": total_in_paid,
        "total_ex_paid_abs": total_ex_paid_abs,
        "net_paid": net_paid,
    }
    return render(request, "transacoes.html", context)



@login_required
@require_POST
def import_fixed(request, kind: str):
    """
    Importa transações FIXAS do mês anterior para o mês atual (sempre PENDENTE).
    Sem heurística por título — parcelamento é verificado pelos campos do modelo.
    kind: 'EX' (despesas) ou 'IN' (receitas).
    """
    if kind not in ("EX", "IN"):
        messages.error(request, "Tipo inválido.")
        return redirect("dashboard")

    # período alvo vindo do formulário (toolbar da página)
    try:
        year = int(request.POST.get("year"))
        month = int(request.POST.get("month"))
    except (TypeError, ValueError):
        today = now().date()
        year, month = today.year, today.month

    # mês anterior
    first_curr = date(year, month, 1)
    first_prev = first_curr - relativedelta(months=1)

    # FIXAS do mês anterior (apenas as que NÃO são parceladas por campo)
    prev_qs = (
        Transaction.objects
        .filter(
            account__owner=request.user,
            date__year=first_prev.year,
            date__month=first_prev.month,
            category__kind=kind,
            is_fixed=True,
            installment_count__isnull=True,   # <<— verificação por campo, não por título
        )
        .select_related("account", "category")
        .order_by("date", "id")
    )

    created = 0
    last_day_curr = calendar.monthrange(year, month)[1]

    for t in prev_qs:
        # mesmo dia (ajustando para meses mais curtos)
        target_day = min(getattr(t.date, "day", 1), last_day_curr)
        target_date = date(year, month, target_day)

        # evita duplicar uma importação idêntica no mês alvo
        exists = Transaction.objects.filter(
            account__owner=request.user,
            date=target_date,
            account=t.account,
            category=t.category,
            description=t.description,
            amount=t.amount,
            is_fixed=True,
            installment_count__isnull=True,
        ).exists()
        if exists:
            continue

        # NÃO enviar group_id para permitir o default do model (evita NOT NULL)
        Transaction.objects.create(
            date=target_date,
            description=t.description,       # mantém “(51/360)” se existir — sem heurística
            account=t.account,
            category=t.category,
            amount=t.amount,                 # mantém sinal (despesa negativa)
            status=TransactionStatus.PENDING,
            is_fixed=True,
            installment_no=None,
            installment_count=None,
        )
        created += 1

    if created:
        messages.success(
            request,
            f"{'Despesas' if kind=='EX' else 'Receitas'} fixas importadas com sucesso ({created}). ✅"
        )
    else:
        messages.info(
            request,
            f"Não havia {'despesas' if kind=='EX' else 'receitas'} fixas para importar do mês anterior."
        )

    target_view = "expenses" if kind == "EX" else "receipts"
    return redirect(f"{reverse(target_view)}?year={year}&month={month}")
