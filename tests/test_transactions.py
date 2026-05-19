from decimal import Decimal
from apps.transactions.models import Account, Transaction
from tests.base import BaseTestCase


class TransactionCreateTests(BaseTestCase):
    """Tests for transaction creation and balance update logic."""

    def setUp(self):
        super().setUp()
        self.acc1 = self.create_account(name='现金', balance=1000)
        self.acc2 = self.create_account(name='银行卡', account_type='bank', balance=5000)
        self.cat_expense = self.create_category(name='餐饮', category_type='expense')
        self.cat_income = self.create_category(name='工资', category_type='income')

    def _reload_account(self, account):
        """Reload account from DB to get the latest balance."""
        return Account.objects.get(id=account.id)

    # ------------------------------------------------------------------
    # 1. Income
    # ------------------------------------------------------------------
    def test_create_income(self):
        """POST /api/transactions/ with income should increase account balance."""
        payload = {
            'account': self.acc1.id,
            'transaction_type': 'income',
            'amount': 100,
            'date': '2026-04-22',
            'category': self.cat_income.id,
            'note': '兼职收入',
        }
        resp = self.client.post('/api/transactions/', payload, format='json')
        self.assertEqual(resp.status_code, 201)

        acc1 = self._reload_account(self.acc1)
        self.assertEqual(acc1.balance, Decimal('1100'))

    # ------------------------------------------------------------------
    # 2. Expense
    # ------------------------------------------------------------------
    def test_create_expense(self):
        """POST /api/transactions/ with expense should decrease account balance."""
        payload = {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 50,
            'date': '2026-04-22',
            'category': self.cat_expense.id,
            'note': '午餐',
        }
        resp = self.client.post('/api/transactions/', payload, format='json')
        self.assertEqual(resp.status_code, 201)

        acc1 = self._reload_account(self.acc1)
        self.assertEqual(acc1.balance, Decimal('950'))

    # ------------------------------------------------------------------
    # 3. Transfer
    # ------------------------------------------------------------------
    def test_create_transfer(self):
        """POST transfer should debit source account and credit destination account."""
        payload = {
            'account': self.acc1.id,
            'to_account': self.acc2.id,
            'transaction_type': 'transfer',
            'amount': 200,
            'date': '2026-04-22',
            'note': '现金存银行',
        }
        resp = self.client.post('/api/transactions/', payload, format='json')
        self.assertEqual(resp.status_code, 201)

        acc1 = self._reload_account(self.acc1)
        acc2 = self._reload_account(self.acc2)
        self.assertEqual(acc1.balance, Decimal('800'))
        self.assertEqual(acc2.balance, Decimal('5200'))

    # ------------------------------------------------------------------
    # 4. Update transaction amount
    # ------------------------------------------------------------------
    def test_update_transaction(self):
        """PATCH amount should revert old balance change and apply new one."""
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 50,
            'date': '2026-04-22',
            'category': self.cat_expense.id,
        }, format='json')
        txn_id = Transaction.objects.latest('id').id

        acc1 = self._reload_account(self.acc1)
        self.assertEqual(acc1.balance, Decimal('950'))

        # PATCH amount from 50 to 80
        # perform_update reverts old amount (50) then applies new (80):
        # 950 + 50 (revert) - 80 (new) = 920
        resp = self.client.patch(
            f'/api/transactions/{txn_id}/',
            {'amount': 80},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

        acc1 = self._reload_account(self.acc1)
        self.assertEqual(acc1.balance, Decimal('920'))

    # ------------------------------------------------------------------
    # 5. Delete transaction
    # ------------------------------------------------------------------
    def test_delete_transaction(self):
        """DELETE should revert the balance change caused by the transaction."""
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 50,
            'date': '2026-04-22',
            'category': self.cat_expense.id,
        }, format='json')
        txn_id = Transaction.objects.latest('id').id

        acc1 = self._reload_account(self.acc1)
        self.assertEqual(acc1.balance, Decimal('950'))

        # Delete -> balance restored to 1000
        resp = self.client.delete(f'/api/transactions/{txn_id}/')
        self.assertEqual(resp.status_code, 204)

        acc1 = self._reload_account(self.acc1)
        self.assertEqual(acc1.balance, Decimal('1000'))

    # ------------------------------------------------------------------
    # 6. Update transaction type / account
    # ------------------------------------------------------------------
    def test_update_transaction_type(self):
        """PATCH changing transaction_type and account should revert old and apply new."""
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 60,
            'date': '2026-04-22',
            'category': self.cat_expense.id,
        }, format='json')
        txn_id = Transaction.objects.latest('id').id

        acc1 = self._reload_account(self.acc1)
        self.assertEqual(acc1.balance, Decimal('940'))

        # Step 2: Change to income on acc2
        # Revert: acc1 +60 -> 1000; Apply income: acc2 +60 -> 5060
        resp = self.client.patch(
            f'/api/transactions/{txn_id}/',
            {
                'transaction_type': 'income',
                'account': self.acc2.id,
                'category': self.cat_income.id,
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

        acc1 = self._reload_account(self.acc1)
        acc2 = self._reload_account(self.acc2)
        self.assertEqual(acc1.balance, Decimal('1000'))
        self.assertEqual(acc2.balance, Decimal('5060'))

    # ------------------------------------------------------------------
    # 7. Transfer balance both sides
    # ------------------------------------------------------------------
    def test_transfer_balance_both_sides(self):
        """Transfer must correctly debit source and credit destination."""
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'to_account': self.acc2.id,
            'transaction_type': 'transfer',
            'amount': 300,
            'date': '2026-04-22',
            'note': '搬家费',
        }, format='json')

        acc1 = self._reload_account(self.acc1)
        acc2 = self._reload_account(self.acc2)
        self.assertEqual(acc1.balance, Decimal('700'))
        self.assertEqual(acc2.balance, Decimal('5300'))

    # ------------------------------------------------------------------
    # 8. Transfer then delete restores both balances
    # ------------------------------------------------------------------
    def test_delete_transfer_restores_both_balances(self):
        """Deleting a transfer must restore both source and destination balances."""
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'to_account': self.acc2.id,
            'transaction_type': 'transfer',
            'amount': 250,
            'date': '2026-04-22',
        }, format='json')
        txn_id = Transaction.objects.latest('id').id

        acc1 = self._reload_account(self.acc1)
        acc2 = self._reload_account(self.acc2)
        self.assertEqual(acc1.balance, Decimal('750'))
        self.assertEqual(acc2.balance, Decimal('5250'))

        self.client.delete(f'/api/transactions/{txn_id}/')

        acc1 = self._reload_account(self.acc1)
        acc2 = self._reload_account(self.acc2)
        self.assertEqual(acc1.balance, Decimal('1000'))
        self.assertEqual(acc2.balance, Decimal('5000'))

    # ------------------------------------------------------------------
    # 9. Amount validation
    # ------------------------------------------------------------------
    def test_create_transaction_negative_amount_rejected(self):
        """Amount must be greater than 0."""
        resp = self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': -10,
            'date': '2026-04-22',
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_create_transaction_zero_amount_rejected(self):
        """Amount of zero must be rejected."""
        resp = self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 0,
            'date': '2026-04-22',
        }, format='json')
        self.assertEqual(resp.status_code, 400)


class TransactionSummaryTests(BaseTestCase):
    """Tests for summary / dashboard endpoints."""

    def setUp(self):
        super().setUp()
        self.acc1 = self.create_account(name='现金', balance=1000)
        self.acc2 = self.create_account(name='银行卡', account_type='bank', balance=5000)
        self.cat_expense = self.create_category(name='餐饮', category_type='expense')
        self.cat_income = self.create_category(name='工资', category_type='income')

    def _create_transactions(self):
        """Helper: create a handful of transactions in the current month."""
        from datetime import date
        today = date.today()
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'income',
            'amount': 500,
            'date': str(today.replace(day=10)),
            'category': self.cat_income.id,
            'note': '工资',
        }, format='json')
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 100,
            'date': str(today.replace(day=10)),
            'category': self.cat_expense.id,
            'note': '早餐午餐',
        }, format='json')
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 200,
            'date': str(today.replace(day=15)),
            'category': self.cat_expense.id,
            'note': '晚餐',
        }, format='json')

    # ------------------------------------------------------------------
    # 8. Daily summary
    # ------------------------------------------------------------------
    def test_daily_summary(self):
        """GET daily_summary returns per-date aggregation for the given month."""
        from datetime import date
        today = date.today()
        self._create_transactions()

        resp = self.client.get('/api/transactions/daily_summary/', {
            'year': today.year, 'month': today.month,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.data

        d10 = str(today.replace(day=10))
        d15 = str(today.replace(day=15))
        dates = {row['date'] for row in data}
        self.assertIn(d10, dates)
        self.assertIn(d15, dates)

        row10 = next(r for r in data if r['date'] == d10)
        self.assertEqual(Decimal(row10['income']), Decimal('500'))
        self.assertEqual(Decimal(row10['expense']), Decimal('100'))

        row15 = next(r for r in data if r['date'] == d15)
        self.assertEqual(Decimal(row15['income']), Decimal('0'))
        self.assertEqual(Decimal(row15['expense']), Decimal('200'))

    # ------------------------------------------------------------------
    # 9. Monthly summary
    # ------------------------------------------------------------------
    def test_monthly_summary(self):
        """GET monthly_summary returns per-month aggregation for the given year."""
        from datetime import date
        today = date.today()
        self._create_transactions()

        resp = self.client.get('/api/transactions/monthly_summary/', {
            'year': today.year,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.data

        month_key = today.strftime('%Y-%m')
        months = {row['month'] for row in data}
        self.assertIn(month_key, months)

        month = next(r for r in data if r['month'] == month_key)
        self.assertEqual(Decimal(month['income']), Decimal('500'))
        self.assertEqual(Decimal(month['expense']), Decimal('300'))
        self.assertEqual(Decimal(month['balance']), Decimal('200'))

    # ------------------------------------------------------------------
    # 10. Category summary
    # ------------------------------------------------------------------
    def test_category_summary(self):
        """GET category_summary returns per-category totals for expenses."""
        from datetime import date
        today = date.today()
        self._create_transactions()

        resp = self.client.get('/api/transactions/category_summary/', {
            'transaction_type': 'expense',
            'year': today.year,
            'month': today.month,
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.data

        self.assertTrue(len(data) >= 1)
        cat = next(r for r in data if r['category_name'] == '餐饮')
        self.assertEqual(Decimal(cat['total']), Decimal('300'))
        self.assertEqual(cat['count'], 2)

    # ------------------------------------------------------------------
    # 11. Dashboard
    # ------------------------------------------------------------------
    def test_dashboard(self):
        """GET dashboard returns month income/expense, total balance, and recent transactions."""
        self._create_transactions()

        resp = self.client.get('/api/transactions/dashboard/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data

        # month_income and month_expense
        self.assertEqual(Decimal(data['month_income']), Decimal('500'))
        self.assertEqual(Decimal(data['month_expense']), Decimal('300'))
        self.assertEqual(Decimal(data['month_balance']), Decimal('200'))

        # total_balance = acc1 + acc2 balances after transactions
        # acc1: 1000 + 500 - 100 - 200 = 1200; acc2: 5000 -> total = 6200
        self.assertEqual(Decimal(data['total_balance']), Decimal('6200'))

        # recent_transactions should include all three
        self.assertTrue(len(data['recent_transactions']) >= 3)

        # today fields exist
        self.assertIn('today_income', data)
        self.assertIn('today_expense', data)


class TransactionFilterTests(BaseTestCase):
    """Tests for transaction list filtering."""

    def setUp(self):
        super().setUp()
        self.acc1 = self.create_account(name='现金', balance=1000)
        self.cat_expense = self.create_category(name='餐饮', category_type='expense')
        self.cat_income = self.create_category(name='工资', category_type='income')

        # Create transactions across different dates and types
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'income',
            'amount': 500,
            'date': '2026-04-10',
            'category': self.cat_income.id,
        }, format='json')
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 100,
            'date': '2026-04-15',
            'category': self.cat_expense.id,
        }, format='json')
        self.client.post('/api/transactions/', {
            'account': self.acc1.id,
            'transaction_type': 'expense',
            'amount': 200,
            'date': '2026-05-01',
            'category': self.cat_expense.id,
        }, format='json')

    # ------------------------------------------------------------------
    # 12. Filter by type
    # ------------------------------------------------------------------
    def test_filter_by_type(self):
        """GET /api/transactions/?transaction_type=expense returns only expenses."""
        resp = self.client.get('/api/transactions/', {
            'transaction_type': 'expense',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results']

        for txn in data:
            self.assertEqual(txn['transaction_type'], 'expense')

        self.assertEqual(len(data), 2)

    # ------------------------------------------------------------------
    # 13. Filter by date range
    # ------------------------------------------------------------------
    def test_filter_by_date_range(self):
        """GET /api/transactions/?start_date=...&end_date=... returns matching rows."""
        resp = self.client.get('/api/transactions/', {
            'start_date': '2026-04-01',
            'end_date': '2026-04-30',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.data['results']

        self.assertEqual(len(data), 2)
        for txn in data:
            self.assertTrue(txn['date'].startswith('2026-04'))
