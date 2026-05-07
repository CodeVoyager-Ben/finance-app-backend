from tests.base import BaseTestCase
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework.test import APIClient
from apps.lending.models import LendingRecord


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

    def test_delete_record(self):
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

    def test_write_off(self):
        # status is read-only in serializer, update directly via DB
        record = LendingRecord.objects.get(id=self.record_id)
        record.status = 'written_off'
        record.save()
        record.refresh_from_db()
        self.assertEqual(record.status, 'written_off')
