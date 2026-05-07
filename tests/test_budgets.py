from tests.base import BaseTestCase
from datetime import date


class BudgetTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.cat = self.create_category(name='餐饮', category_type='expense')

    def test_create_budget(self):
        resp = self.client.post('/api/budgets/', {
            'amount': 2000, 'category': self.cat.id, 'period': 'monthly',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(float(resp.data['amount']), 2000)
        today = date.today()
        self.assertEqual(resp.data['year'], today.year)
        self.assertEqual(resp.data['month'], today.month)

    def test_budget_spent_calculation(self):
        acc = self.create_account(name='现金', balance=10000)
        self.client.post('/api/transactions/', {
            'account': acc.id, 'transaction_type': 'expense',
            'amount': 300, 'category': self.cat.id, 'date': str(date.today()),
        })
        resp = self.client.post('/api/budgets/', {
            'amount': 2000, 'category': self.cat.id, 'period': 'monthly',
        })
        self.assertGreaterEqual(float(resp.data['spent']), 300)

    def test_budget_total_budget(self):
        resp = self.client.post('/api/budgets/', {
            'amount': 10000, 'period': 'monthly',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertIsNone(resp.data['category'])

    def test_list_budgets(self):
        self.client.post('/api/budgets/', {'amount': 1000, 'period': 'monthly'})
        resp = self.client.get('/api/budgets/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_update_budget(self):
        resp = self.client.post('/api/budgets/', {'amount': 1000, 'period': 'monthly'})
        bid = resp.data['id']
        resp = self.client.patch(f'/api/budgets/{bid}/', {'amount': 2000})
        self.assertEqual(float(resp.data['amount']), 2000)

    def test_delete_budget(self):
        resp = self.client.post('/api/budgets/', {'amount': 1000, 'period': 'monthly'})
        resp = self.client.delete(f'/api/budgets/{resp.data["id"]}/')
        self.assertEqual(resp.status_code, 204)
