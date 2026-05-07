from tests.base import BaseTestCase
from apps.investments.models import InvestmentAccount, InvestmentHolding, InvestmentTransaction
from apps.investments.services import to_cny
from decimal import Decimal


class InvestmentAccountTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.asset_type = self.get_asset_type()

    def test_create_investment_account(self):
        resp = self.client.post('/api/investments/', {
            'name': '股票账户', 'asset_type': self.asset_type.id,
            'broker': '招商证券', 'currency': 'CNY',
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], '股票账户')

    def test_list_investment_accounts(self):
        InvestmentAccount.objects.create(
            user=self.user, name='账户A', asset_type=self.asset_type, currency='CNY',
        )
        resp = self.client.get('/api/investments/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_account_summary(self):
        acc = InvestmentAccount.objects.create(
            user=self.user, name='股票账户', asset_type=self.asset_type,
            currency='CNY', balance=10000,
        )
        InvestmentHolding.objects.create(
            investment_account=acc, symbol='600519', name='贵州茅台',
            quantity=10, avg_cost=Decimal('1800'), current_price=Decimal('1900'),
        )
        resp = self.client.get(f'/api/investments/{acc.id}/summary/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['holdings_count'], 1)
        self.assertEqual(float(resp.data['total_market_value']), 19000)


class HoldingTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.asset_type = self.get_asset_type()
        self.invest_acc = InvestmentAccount.objects.create(
            user=self.user, name='股票账户', asset_type=self.asset_type,
            currency='CNY', balance=100000,
        )

    def test_create_holding(self):
        resp = self.client.post('/api/holdings/', {
            'investment_account': self.invest_acc.id,
            'symbol': '000001', 'name': '平安银行',
            'quantity': 1000, 'avg_cost': 12.5, 'current_price': 13.0,
        })
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(float(resp.data['market_value']), 13000)

    def test_holding_dashboard(self):
        InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=10, avg_cost=Decimal('1800'), current_price=Decimal('1900'),
        )
        resp = self.client.get('/api/holdings/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['holdings_count'], 1)

    def test_batch_update_prices(self):
        h = InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=10, avg_cost=Decimal('1800'), current_price=Decimal('1900'),
        )
        resp = self.client.post('/api/holdings/batch_update_prices/', {
            'updates': [{'holding_id': h.id, 'current_price': '1850'}],
        }, format='json')
        self.assertEqual(resp.status_code, 200)
        h.refresh_from_db()
        self.assertEqual(h.current_price, Decimal('1850'))
        self.assertEqual(h.previous_close_price, Decimal('1900'))


class InvestmentTransactionTests(BaseTestCase):

    def setUp(self):
        super().setUp()
        self.asset_type = self.get_asset_type()
        self.invest_acc = InvestmentAccount.objects.create(
            user=self.user, name='股票账户', asset_type=self.asset_type,
            currency='CNY', balance=100000,
        )

    def test_buy_creates_holding(self):
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'buy', 'quantity': 10,
            'price': 1800, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 201)
        h = InvestmentHolding.objects.get(investment_account=self.invest_acc, symbol='600519')
        self.assertEqual(h.quantity, Decimal('10'))
        self.assertEqual(h.avg_cost, Decimal('1800'))

    def test_sell_reduces_holding(self):
        InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=10, avg_cost=Decimal('1800'), current_price=Decimal('1900'),
        )
        self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'sell', 'quantity': 3,
            'price': 1900, 'date': '2026-04-22',
        })
        h = InvestmentHolding.objects.get(investment_account=self.invest_acc, symbol='600519')
        self.assertEqual(h.quantity, Decimal('7'))

    def test_deposit_updates_balance(self):
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': 'CASH', 'name': 'Deposit',
            'transaction_type': 'deposit', 'amount': 5000,
            'date': '2026-04-22',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        # Check via DB query (refresh_from_db may not work due to DecimalField precision)
        acc = InvestmentAccount.objects.get(id=self.invest_acc.id)
        self.assertEqual(float(acc.balance), 105000)


class ExchangeRateTests(BaseTestCase):

    def test_to_cny_same_currency(self):
        self.assertEqual(to_cny(Decimal('100'), 'CNY'), Decimal('100'))

    def test_to_cny_no_rate(self):
        result = to_cny(Decimal('100'), 'USD')
        self.assertEqual(result, Decimal('100'))


class AssetTypeTests(BaseTestCase):

    def test_list_asset_types(self):
        self.get_asset_type()
        resp = self.client.get('/api/asset-types/')
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.data), 1)

    def test_create_custom_asset_type(self):
        resp = self.client.post('/api/asset-types/', {
            'code': 'custom1', 'name': '自定义类型',
            'category': 'other', 'icon': '🎯', 'color': '#333',
        })
        self.assertEqual(resp.status_code, 201)
