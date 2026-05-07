from datetime import date
from decimal import Decimal

from tests.base import BaseTestCase
from apps.lending.models import LendingRecord
from apps.transactions.models import Transaction


class BalanceSheetTests(BaseTestCase):
    """Tests for GET /api/reports/balance-sheet/"""

    url = '/api/reports/balance-sheet/'

    def test_balance_sheet_empty(self):
        """No data -- check response structure."""
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Top-level keys
        self.assertIn('assets', data)
        self.assertIn('liabilities', data)
        self.assertIn('net_worth', data)
        self.assertIn('ratios', data)

        # Asset structure
        assets = data['assets']
        self.assertIn('cash', assets)
        self.assertIn('total', assets)
        self.assertIn('allocation', assets)
        self.assertIn('investments', assets)
        self.assertIn('receivables', assets)
        self.assertIn('invest_balance', assets)
        self.assertEqual(assets['cash']['total'], 0)
        self.assertEqual(assets['investments']['total'], 0)
        self.assertEqual(assets['receivables']['total'], 0)
        self.assertEqual(assets['total'], 0)

        # Liability structure
        liabilities = data['liabilities']
        self.assertIn('items', liabilities)
        self.assertIn('payables', liabilities)
        self.assertIn('total', liabilities)
        self.assertEqual(liabilities['total'], 0)

        # Net worth should be 0
        self.assertEqual(data['net_worth'], 0)

        # Ratios keys
        ratios = data['ratios']
        for key in ('debt_ratio', 'current_ratio', 'savings_ratio',
                     'investment_ratio', 'health_level'):
            self.assertIn(key, ratios)

    def test_balance_sheet_with_cash(self):
        """Accounts with positive balances appear as cash assets."""
        self.create_account(name='Wallet', balance=500)
        self.create_account(name='Bank', balance=3000, account_type='bank')

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        cash_items = data['assets']['cash']['items']
        self.assertEqual(len(cash_items), 2)
        names = {item['name'] for item in cash_items}
        self.assertIn('Wallet', names)
        self.assertIn('Bank', names)
        self.assertEqual(data['assets']['cash']['total'], 3500)

    def test_balance_sheet_with_liabilities(self):
        """Account with negative balance appears under liabilities."""
        self.create_account(name='Credit Card', balance=-2000, account_type='credit_card')

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        liabilities_items = data['liabilities']['items']
        self.assertEqual(len(liabilities_items), 1)
        self.assertEqual(liabilities_items[0]['name'], 'Credit Card')
        self.assertEqual(liabilities_items[0]['amount'], 2000)
        self.assertGreater(data['liabilities']['total'], 0)

    def test_balance_sheet_exclude_from_reports(self):
        """Accounts with exclude_from_reports=True are excluded from the balance sheet."""
        self.create_account(name='Hidden', balance=9999, exclude_from_reports=True)
        self.create_account(name='Visible', balance=1000, exclude_from_reports=False)

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        cash_items = data['assets']['cash']['items']
        names = {item['name'] for item in cash_items}
        self.assertNotIn('Hidden', names)
        self.assertIn('Visible', names)
        self.assertEqual(data['assets']['cash']['total'], 1000)

    def test_balance_sheet_net_worth(self):
        """Net worth = total assets - total liabilities."""
        self.create_account(name='Savings', balance=10000, account_type='bank')
        self.create_account(name='Card', balance=-3000, account_type='credit_card')

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        total_assets = data['assets']['total']
        total_liabilities = data['liabilities']['total']
        self.assertEqual(data['net_worth'], total_assets - total_liabilities)
        self.assertEqual(data['net_worth'], 7000)

    def test_balance_sheet_with_lending(self):
        """Lend/borrow records produce receivables and payables."""
        LendingRecord.objects.create(
            user=self.user, record_type='lend',
            counterparty='张三', amount=1000,
            date=date(2026, 1, 1),
        )
        LendingRecord.objects.create(
            user=self.user, record_type='borrow',
            counterparty='李四', amount=2000,
            date=date(2026, 1, 1),
        )

        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Receivables (lend)
        receivables = data['assets']['receivables']['items']
        self.assertEqual(len(receivables), 1)
        self.assertEqual(receivables[0]['name'], '张三')
        self.assertEqual(receivables[0]['amount'], 1000)
        self.assertEqual(data['assets']['receivables']['total'], 1000)

        # Payables (borrow)
        payables = data['liabilities']['payables']['items']
        self.assertEqual(len(payables), 1)
        self.assertEqual(payables[0]['name'], '李四')
        self.assertEqual(payables[0]['amount'], 2000)
        self.assertEqual(data['liabilities']['payables']['total'], 2000)

    def test_balance_sheet_historical_date(self):
        """Passing ?date= returns a response with that date."""
        resp = self.client.get(self.url, {'date': '2026-01-01'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['date'], '2026-01-01')


class NetWorthHistoryTests(BaseTestCase):
    """Tests for GET /api/reports/net-worth-history/"""

    url = '/api/reports/net-worth-history/'

    def test_net_worth_history(self):
        """Response contains a history list with month entries."""
        resp = self.client.get(self.url, {'months': 6})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn('history', data)
        self.assertIsInstance(data['history'], list)
        self.assertGreater(len(data['history']), 0)

        for entry in data['history']:
            self.assertIn('month', entry)
            self.assertIn('assets', entry)
            self.assertIn('liabilities', entry)
            self.assertIn('net_worth', entry)

    def test_net_worth_history_with_data(self):
        """Creating transactions should be reflected in the history."""
        acc = self.create_account(name='Bank', balance=5000, account_type='bank')
        cat = self.create_category(name='Salary', category_type='income')

        Transaction.objects.create(
            user=self.user, account=acc, category=cat,
            transaction_type='income', amount=Decimal('3000'),
            date=date(2026, 3, 15),
        )

        resp = self.client.get(self.url, {'months': 6})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # The history list should contain entries
        self.assertIsInstance(data['history'], list)
        self.assertGreater(len(data['history']), 1)

        # The most recent entry should reflect current assets (5000 balance)
        current = data['history'][-1]
        self.assertEqual(current['month'], date.today().strftime('%Y-%m'))
        self.assertGreaterEqual(current['assets'], 5000)


class ExportExcelTests(BaseTestCase):
    """Tests for GET /api/reports/export/"""

    url = '/api/reports/export/'

    def test_export_transactions(self):
        """Exporting transactions returns an xlsx file."""
        resp = self.client.get(self.url, {'type': 'transactions'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('filename=', resp['Content-Disposition'])
        self.assertIn('.xlsx', resp['Content-Disposition'])

    def test_export_balance_sheet(self):
        """Exporting balance sheet returns an xlsx file."""
        resp = self.client.get(self.url, {'type': 'balance_sheet'})
        self.assertEqual(resp.status_code, 200)

        self.assertEqual(
            resp['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('filename=', resp['Content-Disposition'])
        self.assertIn('.xlsx', resp['Content-Disposition'])

    def test_export_invalid_type(self):
        """An unsupported export type returns 400."""
        resp = self.client.get(self.url, {'type': 'invalid'})
        self.assertEqual(resp.status_code, 400)
