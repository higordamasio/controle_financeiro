import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Account(models.Model):
    name = models.CharField(max_length=80)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    initial_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.name


class Category(models.Model):
    INCOME = "IN"
    EXPENSE = "EX"

    KIND_CHOICES = (
        (INCOME, "Receita"),
        (EXPENSE, "Despesa"),
    )

    name = models.CharField(max_length=80)
    kind = models.CharField(max_length=2, choices=KIND_CHOICES)

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"


class TransactionStatus(models.TextChoices):
    PENDING = "PEN", "Pendente"
    PAID    = "PAG", "Paga"


class Transaction(models.Model):
    date = models.DateField()
    description = models.CharField(max_length=140)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="transactions")
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # + receita; - despesa

    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=3,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
    )
    updated_at = models.DateTimeField(auto_now=True)

    # Parcelamento
    group_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)  # identifica o "grupo" de parcelas
    installment_no = models.PositiveSmallIntegerField(null=True, blank=True)        # número da parcela (1..N)
    installment_count = models.PositiveSmallIntegerField(null=True, blank=True)     # total de parcelas (N)

    # NOVO: Flag para recorrência simples (sem parcelas)
    is_fixed = models.BooleanField(default=False, verbose_name="Despesa/Receita fixa")

    class Meta:
        ordering = ["-date", "-id"]
        indexes = [
            models.Index(fields=["is_fixed"]),
        ]

    def __str__(self):
        return f"{self.date} • {self.description} • {self.amount}"
