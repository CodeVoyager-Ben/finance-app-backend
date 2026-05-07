from tests.base import BaseTestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken


class AccountTests(BaseTestCase):

    def test_create_account(self):
        resp = self.client.post('/api/accounts/', {
            'name': '招商银行', 'account_type': 'bank',
            'balance': 5000, 'icon': '🏦', 'color': '#722ed1',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], '招商银行')
        self.assertEqual(float(resp.data['balance']), 5000)

    def test_list_accounts(self):
        self.create_account(name='现金')
        self.create_account(name='银行卡', account_type='bank')
        resp = self.client.get('/api/accounts/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_retrieve_account(self):
        acc = self.create_account(name='支付宝', account_type='alipay')
        resp = self.client.get(f'/api/accounts/{acc.id}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], '支付宝')

    def test_update_account(self):
        acc = self.create_account(name='旧名称')
        resp = self.client.patch(f'/api/accounts/{acc.id}/', {'name': '新名称'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], '新名称')

    def test_delete_account(self):
        acc = self.create_account(name='待删除')
        resp = self.client.delete(f'/api/accounts/{acc.id}/')
        self.assertEqual(resp.status_code, 204)

    def test_exclude_from_reports_default(self):
        resp = self.client.post('/api/accounts/', {
            'name': '测试', 'account_type': 'cash', 'balance': 0,
        })
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data['exclude_from_reports'])

    def test_set_exclude_from_reports(self):
        acc = self.create_account(name='隐藏账户')
        self.client.patch(f'/api/accounts/{acc.id}/', {'exclude_from_reports': True})
        resp = self.client.get(f'/api/accounts/{acc.id}/')
        self.assertTrue(resp.data['exclude_from_reports'])

    def test_data_isolation(self):
        self.create_account(name='用户1的账户')
        acc2 = self.create_account(name='用户2的账户', user=self.user2)
        token2 = str(AccessToken.for_user(self.user2))
        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f'Bearer {token2}')

        resp = client2.get('/api/accounts/')
        data = resp.data.get('results', resp.data) if isinstance(resp.data, dict) else resp.data
        names = [a['name'] for a in data]
        self.assertIn('用户2的账户', names)
        self.assertNotIn('用户1的账户', names)
