from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Account, Category, Transaction, TransactionStatus


User = get_user_model()


class ExpensesViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="higor",
            password="teste123",
        )
        self.client.force_login(self.user)
        self.account = Account.objects.create(name="Carteira", owner=self.user)
        self.category = Category.objects.create(name="Cartao", kind=Category.EXPENSE)

    def test_marks_section_as_paid_only_when_all_transactions_are_paid(self):
        Transaction.objects.create(
            date=date(2026, 3, 10),
            description="Parcela 1",
            account=self.account,
            category=self.category,
            amount=Decimal("-100.00"),
            status=TransactionStatus.PAID,
        )
        Transaction.objects.create(
            date=date(2026, 3, 15),
            description="Parcela 2",
            account=self.account,
            category=self.category,
            amount=Decimal("-50.00"),
            status=TransactionStatus.PENDING,
        )

        response = self.client.get(reverse("expenses"), {"year": 2026, "month": 3})

        section = response.context["sections"][0]
        self.assertFalse(section["all_paid"])

    def test_marks_section_as_paid_when_every_transaction_is_paid(self):
        Transaction.objects.create(
            date=date(2026, 3, 10),
            description="Parcela 1",
            account=self.account,
            category=self.category,
            amount=Decimal("-100.00"),
            status=TransactionStatus.PAID,
        )
        Transaction.objects.create(
            date=date(2026, 3, 15),
            description="Parcela 2",
            account=self.account,
            category=self.category,
            amount=Decimal("-50.00"),
            status=TransactionStatus.PAID,
        )

        response = self.client.get(reverse("expenses"), {"year": 2026, "month": 3})

        section = response.context["sections"][0]
        self.assertTrue(section["all_paid"])
