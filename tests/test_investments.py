from tests.base import BaseTestCase
from apps.investments.models import (
    InvestmentAccount, InvestmentHolding, InvestmentTransaction,
    DividendRecord, DailyHoldingSnapshot, ExchangeRate,
)
from apps.investments.services import to_cny, update_holding_from_transaction, handle_dividend
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

    def test_edit_account_balance_creates_adjustment(self):
        acc = InvestmentAccount.objects.create(
            user=self.user, name='股票账户', asset_type=self.asset_type,
            currency='CNY', balance=10000,
        )
        resp = self.client.patch(f'/api/investments/{acc.id}/', {'balance': 99999})
        self.assertEqual(resp.status_code, 200)
        acc.refresh_from_db()
        # 余额已更新为新值
        self.assertEqual(acc.balance, Decimal('99999'))
        # 自动生成一笔 deposit 调整流水，金额为差额
        tx = InvestmentTransaction.objects.filter(
            investment_account=acc, transaction_type='deposit', note='余额调整',
        )
        self.assertEqual(tx.count(), 1)
        self.assertEqual(tx.first().amount, Decimal('89999'))


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


class BuySellBalanceTests(BaseTestCase):
    """买入/卖出应正确更新投资账户余额"""

    def setUp(self):
        super().setUp()
        self.asset_type = self.get_asset_type()
        self.invest_acc = InvestmentAccount.objects.create(
            user=self.user, name='股票账户', asset_type=self.asset_type,
            currency='CNY', balance=100000,
        )

    def test_buy_deducts_balance(self):
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'buy', 'quantity': 10,
            'price': 1000, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 201)
        acc = InvestmentAccount.objects.get(id=self.invest_acc.id)
        # amount = 10 * 1000 = 10000, fee auto-calculated
        fee = Decimal(resp.data['fee'])
        expected = Decimal('100000') - (Decimal('10000') + fee)
        self.assertEqual(acc.balance, expected)

    def test_sell_adds_balance(self):
        InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=10, avg_cost=Decimal('1000'), current_price=Decimal('1000'),
        )
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'sell', 'quantity': 5,
            'price': 1200, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 201)
        acc = InvestmentAccount.objects.get(id=self.invest_acc.id)
        # amount = 5 * 1200 = 6000, fee auto-calculated
        fee = Decimal(resp.data['fee'])
        expected = Decimal('100000') + (Decimal('6000') - fee)
        self.assertEqual(acc.balance, expected)

    def test_deposit_adds_balance(self):
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': 'CASH', 'name': 'Deposit',
            'transaction_type': 'deposit', 'amount': 5000,
            'date': '2026-04-22',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        acc = InvestmentAccount.objects.get(id=self.invest_acc.id)
        self.assertEqual(acc.balance, Decimal('105000'))

    def test_withdraw_deducts_balance(self):
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': 'CASH', 'name': 'Withdraw',
            'transaction_type': 'withdraw', 'amount': 3000,
            'date': '2026-04-22',
        }, format='json')
        self.assertEqual(resp.status_code, 201)
        acc = InvestmentAccount.objects.get(id=self.invest_acc.id)
        self.assertEqual(acc.balance, Decimal('97000'))


class HoldingUpdateTests(BaseTestCase):
    """持仓更新逻辑"""

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
        # avg_cost includes fee: (1800*10 + fee) / 10 ≈ 1800.52
        self.assertAlmostEqual(float(h.avg_cost), 1800.0, delta=1)

    def test_multi_buy_avg_cost(self):
        """多次买入计算加权均价"""
        self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'buy', 'quantity': 10,
            'price': 100, 'date': '2026-01-01',
        })
        self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'buy', 'quantity': 10,
            'price': 200, 'date': '2026-01-02',
        })
        h = InvestmentHolding.objects.get(investment_account=self.invest_acc, symbol='600519')
        self.assertEqual(h.quantity, Decimal('20'))
        # avg_cost includes fees: ≈ 150.5
        self.assertAlmostEqual(float(h.avg_cost), 150.5, delta=1)

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

    def test_sell_all_clears_holding(self):
        """全部卖出后持仓归零"""
        InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=10, avg_cost=Decimal('1800'), current_price=Decimal('1900'),
        )
        self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'sell', 'quantity': 10,
            'price': 1900, 'date': '2026-04-22',
        })
        h = InvestmentHolding.objects.get(investment_account=self.invest_acc, symbol='600519')
        self.assertEqual(h.quantity, Decimal('0'))
        self.assertEqual(h.avg_cost, Decimal('0'))

    def test_sell_over_quantity_rejected(self):
        InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=5, avg_cost=Decimal('1800'), current_price=Decimal('1900'),
        )
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'sell', 'quantity': 10,
            'price': 1900, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_split_adjusts_quantity_and_cost(self):
        """拆股：数量按比例增加，成本按比例降低"""
        InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=100, avg_cost=Decimal('1800'), current_price=Decimal('1800'),
        )
        txn = InvestmentTransaction.objects.create(
            investment_account=self.invest_acc,
            symbol='600519', name='贵州茅台',
            transaction_type='split', quantity=2,
            price=0, amount=0, date='2026-04-22',
        )
        update_holding_from_transaction(txn)
        h = InvestmentHolding.objects.get(investment_account=self.invest_acc, symbol='600519')
        self.assertEqual(h.quantity, Decimal('200'))
        self.assertEqual(h.avg_cost, Decimal('900'))


class DividendTests(BaseTestCase):
    """分红处理"""

    def setUp(self):
        super().setUp()
        self.asset_type = self.get_asset_type()
        self.invest_acc = InvestmentAccount.objects.create(
            user=self.user, name='股票账户', asset_type=self.asset_type,
            currency='CNY', balance=50000,
        )
        self.holding = InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=100, avg_cost=Decimal('1800'), current_price=Decimal('1800'),
        )

    def test_cash_dividend_increases_balance(self):
        """现金分红：账户余额增加"""
        record = DividendRecord.objects.create(
            investment_account=self.invest_acc,
            holding=self.holding,
            symbol='600519', name='贵州茅台',
            dividend_type='cash',
            ex_date='2026-04-22',
            dividend_per_unit=Decimal('21.37'),
            quantity=Decimal('100'),
            total_amount=Decimal('2137'),
            net_amount=Decimal('2137'),
        )
        handle_dividend(record)
        acc = InvestmentAccount.objects.get(id=self.invest_acc.id)
        self.assertEqual(acc.balance, Decimal('50000') + Decimal('2137'))

    def test_cash_dividend_updates_accumulated(self):
        """现金分红：累计分红增加"""
        record = DividendRecord.objects.create(
            investment_account=self.invest_acc,
            holding=self.holding,
            symbol='600519', name='贵州茅台',
            dividend_type='cash',
            ex_date='2026-04-22',
            dividend_per_unit=Decimal('21.37'),
            quantity=Decimal('100'),
            total_amount=Decimal('2137'),
            net_amount=Decimal('2137'),
        )
        handle_dividend(record)
        h = InvestmentHolding.objects.get(id=self.holding.id)
        self.assertEqual(h.accumulated_dividend, Decimal('2137'))

    def test_reinvest_does_not_change_balance(self):
        """分红再投资：账户余额不变"""
        record = DividendRecord.objects.create(
            investment_account=self.invest_acc,
            holding=self.holding,
            symbol='600519', name='贵州茅台',
            dividend_type='reinvest',
            ex_date='2026-04-22',
            dividend_per_unit=Decimal('10'),
            quantity=Decimal('100'),
            total_amount=Decimal('1000'),
            net_amount=Decimal('1000'),
        )
        handle_dividend(record)
        acc = InvestmentAccount.objects.get(id=self.invest_acc.id)
        # 余额不应变化
        self.assertEqual(acc.balance, Decimal('50000'))

    def test_reinvest_increases_holding_quantity(self):
        """分红再投资：持仓数量增加"""
        record = DividendRecord.objects.create(
            investment_account=self.invest_acc,
            holding=self.holding,
            symbol='600519', name='贵州茅台',
            dividend_type='reinvest',
            ex_date='2026-04-22',
            dividend_per_unit=Decimal('10'),
            quantity=Decimal('100'),
            total_amount=Decimal('1000'),
            net_amount=Decimal('1000'),
        )
        handle_dividend(record)
        h = InvestmentHolding.objects.get(id=self.holding.id)
        # reinvest_qty = 1000 / 1800 ≈ 0.5556
        self.assertGreater(h.quantity, Decimal('100'))

    def test_interest_increases_balance(self):
        """利息收入：账户余额增加"""
        record = DividendRecord.objects.create(
            investment_account=self.invest_acc,
            holding=self.holding,
            symbol='600519', name='贵州茅台',
            dividend_type='interest',
            ex_date='2026-04-22',
            dividend_per_unit=Decimal('5'),
            quantity=Decimal('100'),
            total_amount=Decimal('500'),
            net_amount=Decimal('500'),
        )
        handle_dividend(record)
        acc = InvestmentAccount.objects.get(id=self.invest_acc.id)
        self.assertEqual(acc.balance, Decimal('50500'))


class ValidationTests(BaseTestCase):
    """数据验证"""

    def setUp(self):
        super().setUp()
        self.asset_type = self.get_asset_type()
        self.invest_acc = InvestmentAccount.objects.create(
            user=self.user, name='我的账户', asset_type=self.asset_type,
            currency='CNY', balance=100000,
        )
        # 另一个用户的账户
        self.other_acc = InvestmentAccount.objects.create(
            user=self.user2, name='别人的账户', asset_type=self.asset_type,
            currency='CNY', balance=50000,
        )

    def test_cannot_trade_on_others_account(self):
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.other_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'buy', 'quantity': 10,
            'price': 100, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_holding_must_belong_to_account(self):
        other_holding = InvestmentHolding.objects.create(
            investment_account=self.other_acc, symbol='000001', name='平安银行',
            quantity=100, avg_cost=Decimal('10'), current_price=Decimal('12'),
        )
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'holding': other_holding.id,
            'symbol': '000001', 'name': '平安银行',
            'transaction_type': 'buy', 'quantity': 10,
            'price': 12, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_buy_requires_positive_qty_and_price(self):
        resp = self.client.post('/api/invest-trans/', {
            'investment_account': self.invest_acc.id,
            'symbol': '600519', 'name': '贵州茅台',
            'transaction_type': 'buy', 'quantity': 0,
            'price': 100, 'date': '2026-04-22',
        })
        self.assertEqual(resp.status_code, 400)

    def test_dividend_amount_validation(self):
        resp = self.client.post('/api/dividend-records/', {
            'investment_account': self.invest_acc.id,
            'holding': self.holding_id(),
            'symbol': '600519', 'name': '贵州茅台',
            'dividend_type': 'cash',
            'ex_date': '2026-04-22',
            'dividend_per_unit': 10, 'quantity': 100,
            'total_amount': 999,  # wrong: should be 10*100=1000
            'net_amount': 999,
        }, format='json')
        self.assertEqual(resp.status_code, 400)

    def holding_id(self):
        h, _ = InvestmentHolding.objects.get_or_create(
            investment_account=self.invest_acc, symbol='600519',
            defaults={'name': '贵州茅台', 'quantity': 100,
                      'avg_cost': Decimal('1800'), 'current_price': Decimal('1800')},
        )
        return h.id


class FeeCalculationTests(BaseTestCase):
    """手续费计算"""

    def test_buy_fees_no_stamp_duty(self):
        from apps.investments.fee_calculator import calculate_buy_fees
        fees = calculate_buy_fees(Decimal('100'), Decimal('1000'))
        self.assertEqual(fees['stamp_duty'], Decimal('0'))
        # commission = max(100000 * 0.00025, 5) = max(25, 5) = 25
        self.assertEqual(fees['commission'], Decimal('25.00'))
        # transfer_fee = 100000 * 0.00001 = 1
        self.assertEqual(fees['transfer_fee'], Decimal('1.00'))

    def test_sell_fees_include_stamp_duty(self):
        from apps.investments.fee_calculator import calculate_sell_fees
        fees = calculate_sell_fees(Decimal('100'), Decimal('1000'))
        # stamp_duty = 100000 * 0.0005 = 50
        self.assertEqual(fees['stamp_duty'], Decimal('50.00'))

    def test_min_commission(self):
        from apps.investments.fee_calculator import calculate_buy_fees
        # Small trade: 1 * 10 = 10, commission = 10 * 0.00025 = 0.0025 < 5
        fees = calculate_buy_fees(Decimal('1'), Decimal('10'))
        self.assertEqual(fees['commission'], Decimal('5.00'))


class ExchangeRateTests(BaseTestCase):

    def test_to_cny_same_currency(self):
        self.assertEqual(to_cny(Decimal('100'), 'CNY'), Decimal('100'))

    def test_to_cny_with_rate(self):
        ExchangeRate.objects.create(
            target_currency='USD', rate=Decimal('7.25'),
            rate_date='2026-05-01',
        )
        result = to_cny(Decimal('100'), 'USD')
        self.assertEqual(result, Decimal('725'))

    def test_to_cny_no_rate_returns_zero(self):
        """无汇率记录时返回 0，而非静默返回外币金额"""
        result = to_cny(Decimal('100'), 'EUR')
        self.assertEqual(result, Decimal('0'))


class SnapshotTests(BaseTestCase):
    """快照相关测试"""

    def setUp(self):
        super().setUp()
        self.asset_type = self.get_asset_type()
        self.invest_acc = InvestmentAccount.objects.create(
            user=self.user, name='股票账户', asset_type=self.asset_type,
            currency='CNY', balance=100000,
        )

    def test_batch_update_creates_no_snapshot(self):
        """手动批量更新价格不应创建快照（只有 auto_update 才创建）"""
        h = InvestmentHolding.objects.create(
            investment_account=self.invest_acc, symbol='600519', name='贵州茅台',
            quantity=10, avg_cost=Decimal('1800'), current_price=Decimal('1900'),
        )
        self.client.post('/api/holdings/batch_update_prices/', {
            'updates': [{'holding_id': h.id, 'current_price': '1850'}],
        }, format='json')
        self.assertEqual(DailyHoldingSnapshot.objects.count(), 0)


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
