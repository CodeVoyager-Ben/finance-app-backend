from decimal import Decimal
from tests.base import BaseTestCase
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.test import APIClient
from apps.lending.models import LendingRecord, Repayment


class LendingRecordTests(BaseTestCase):

    def test_create_lend_record(self):
        resp = self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['counterparty'], '张三')
        self.assertEqual(float(resp.data['amount']), 1000)

    def test_create_borrow_record(self):
        resp = self.client.post('/api/lending-records/', {
            'record_type': 'borrow', 'counterparty': '李四',
            'amount': 500, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['record_type'], 'borrow')

    def test_list_records(self):
        self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-22',
        })
        resp = self.client.get('/api/lending-records/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data.get('results', resp.data)
        self.assertGreaterEqual(len(data), 1)

    def test_update_record(self):
        self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-22',
        })
        rid = LendingRecord.objects.latest('id').id
        resp = self.client.patch(f'/api/lending-records/{rid}/', {'amount': 1500})
        self.assertEqual(resp.status_code, 200)
        record = self.client.get(f'/api/lending-records/{rid}/').data
        self.assertEqual(float(record['amount']), 1500)

    def test_delete_record_without_repayments(self):
        self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-22',
        })
        rid = LendingRecord.objects.latest('id').id
        resp = self.client.delete(f'/api/lending-records/{rid}/')
        self.assertEqual(resp.status_code, 204)

    def test_filter_by_type(self):
        self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': 'A',
            'amount': 100, 'date': '2026-04-22',
        })
        self.client.post('/api/lending-records/', {
            'record_type': 'borrow', 'counterparty': 'B',
            'amount': 200, 'date': '2026-04-22',
        })
        resp = self.client.get('/api/lending-records/', {'record_type': 'lend'})
        data = resp.data.get('results', resp.data)
        self.assertTrue(all(r['record_type'] == 'lend' for r in data))

    def test_summary(self):
        self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-22',
        })
        self.client.post('/api/lending-records/', {
            'record_type': 'borrow', 'counterparty': '李四',
            'amount': 500, 'date': '2026-04-22',
        })
        resp = self.client.get('/api/lending-records/summary/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(float(resp.data['total_lent']), 1000)
        self.assertGreaterEqual(float(resp.data['total_borrowed']), 500)

    def test_write_off_via_api(self):
        """核销功能应通过专用端点工作"""
        self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-22',
        })
        rid = LendingRecord.objects.latest('id').id
        resp = self.client.post(f'/api/lending-records/{rid}/write-off/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'written_off')

    def test_write_off_settled_record_rejected(self):
        """已结清记录不能核销"""
        self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-22',
        })
        rid = LendingRecord.objects.latest('id').id
        # 全额还款 → 结清
        self.client.post('/api/repayments/', {
            'lending_record': rid, 'repay_type': 'collect',
            'amount': 1000, 'date': '2026-04-22',
        })
        resp = self.client.post(f'/api/lending-records/{rid}/write-off/')
        self.assertEqual(resp.status_code, 400)

    def test_delete_record_with_repayments_reverts_balance(self):
        """删除借贷记录时，应回退还款的账户余额"""
        acc = self.create_account(balance=5000)
        self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-22',
            'account': acc.id,
        })
        rid = LendingRecord.objects.latest('id').id
        # 收款 500
        self.client.post('/api/repayments/', {
            'lending_record': rid, 'repay_type': 'collect',
            'amount': 500, 'account': acc.id, 'date': '2026-04-22',
        })
        # 余额应变为 5000 + 500 = 5500
        acc.refresh_from_db()
        self.assertEqual(acc.balance, Decimal('5500'))

        # 删除借贷记录
        self.client.delete(f'/api/lending-records/{rid}/')
        # 余额应回退到 5000
        acc.refresh_from_db()
        self.assertEqual(acc.balance, Decimal('5000'))


class RepaymentTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        resp = self.client.post('/api/lending-records/', {
            'record_type': 'lend', 'counterparty': '张三',
            'amount': 1000, 'date': '2026-04-01',
        })
        self.record_id = LendingRecord.objects.latest('id').id

    def test_repay_updates_status_to_partial(self):
        resp = self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 300,
            'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 201)
        record = self.client.get(f'/api/lending-records/{self.record_id}/').data
        self.assertEqual(float(record['repaid_amount']), 300)
        self.assertEqual(record['status'], 'partial')

    def test_repay_full_settles(self):
        self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 1000,
            'date': '2026-04-22',
        })
        record = self.client.get(f'/api/lending-records/{self.record_id}/').data
        self.assertEqual(record['status'], 'settled')

    def test_repay_exceeds_remaining_rejected(self):
        resp = self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 1500,
            'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_repay_other_user_record_rejected(self):
        token2 = str(AccessToken.for_user(self.user2))
        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f'Bearer {token2}')
        resp = client2.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 100,
            'date': '2026-04-22',
        })
        self.assertIn(resp.status_code, [400, 403])

    def test_wrong_repay_type_for_lend(self):
        """借出记录只能收款(collect)，不能还款(repay)"""
        resp = self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'repay', 'amount': 100,
            'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_wrong_repay_type_for_borrow(self):
        """借入记录只能还款(repay)，不能收款(collect)"""
        self.client.post('/api/lending-records/', {
            'record_type': 'borrow', 'counterparty': '李四',
            'amount': 500, 'date': '2026-04-01',
        })
        borrow_id = LendingRecord.objects.filter(record_type='borrow').latest('id').id
        resp = self.client.post('/api/repayments/', {
            'lending_record': borrow_id,
            'repay_type': 'collect', 'amount': 100,
            'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_interest_exceeds_amount_rejected(self):
        """利息不能超过还款总额"""
        resp = self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 100,
            'interest': 200, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_repay_settled_record_rejected(self):
        """已结清记录不允许还款"""
        self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 1000,
            'date': '2026-04-22',
        })
        resp = self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 50,
            'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_repay_written_off_record_rejected(self):
        """已核销记录不允许还款"""
        self.client.post(f'/api/lending-records/{self.record_id}/write-off/')
        resp = self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 100,
            'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_repayment_updates_account_balance(self):
        """还款应更新关联账户余额"""
        acc = self.create_account(balance=5000)
        resp = self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 500,
            'account': acc.id, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 201)
        acc.refresh_from_db()
        self.assertEqual(acc.balance, Decimal('5500'))

    def test_delete_repayment_reverts_balance(self):
        """删除还款应回退账户余额"""
        acc = self.create_account(balance=5000)
        self.client.post('/api/repayments/', {
            'lending_record': self.record_id,
            'repay_type': 'collect', 'amount': 500,
            'account': acc.id, 'date': '2026-04-22',
        })
        # 删除还款
        rid = Repayment.objects.latest('id').id
        self.client.delete(f'/api/repayments/{rid}/')
        acc.refresh_from_db()
        self.assertEqual(acc.balance, Decimal('5000'))
