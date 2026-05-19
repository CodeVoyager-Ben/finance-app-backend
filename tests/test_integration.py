"""跨模块集成测试：验证各模块间的交互逻辑"""

from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.transactions.models import Account, Category, Transaction, Budget
from apps.investments.models import (
    InvestmentAccount, InvestmentHolding, DailyHoldingSnapshot, AssetType,
)
from apps.lending.models import LendingRecord, Repayment
from apps.investments.services import to_cny
from django.contrib.auth import get_user_model

User = get_user_model()

TODAY = date.today()


class IntegrationBaseTestCase(TestCase):
    """集成测试基类"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='intuser', password='TestPass123!', email='int@example.com'
        )
        self.token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        # 创建基础数据
        self.account = Account.objects.create(
            user=self.user, name='现金账户', account_type='cash',
            balance=10000, icon='💵', color='#1677ff',
        )
        self.credit_card = Account.objects.create(
            user=self.user, name='信用卡', account_type='credit_card',
            balance=-2000, icon='💳', color='#722ed1',
        )
        self.category = Category.objects.create(
            user=self.user, name='餐饮', category_type='expense',
            icon='🍽️', color='#ff4d4f',
        )
        self.income_cat = Category.objects.create(
            user=self.user, name='工资', category_type='income',
            icon='💰', color='#52c41a',
        )

    def create_transaction(self, **kwargs):
        defaults = {
            'user': self.user, 'transaction_type': 'expense',
            'amount': 100, 'account': self.account,
            'category': self.category, 'date': TODAY,
        }
        defaults.update(kwargs)
        return Transaction.objects.create(**defaults)


class TransferAndReportsTest(IntegrationBaseTestCase):
    """转账不应计入收支统计"""

    def test_transfer_excluded_from_income_expense(self):
        target = Account.objects.create(
            user=self.user, name='储蓄账户', account_type='bank', balance=0
        )
        # 转账 500
        Transaction.objects.create(
            user=self.user, transaction_type='transfer', amount=500,
            account=self.account, to_account=target, date=TODAY,
        )
        # 收入 1000
        Transaction.objects.create(
            user=self.user, transaction_type='income', amount=1000,
            account=self.account, category=self.income_cat, date=TODAY,
        )
        # 支出 200
        Transaction.objects.create(
            user=self.user, transaction_type='expense', amount=200,
            account=self.account, category=self.category, date=TODAY,
        )

        resp = self.client.get('/api/transactions/filter_summary/')
        self.assertEqual(resp.status_code, 200)
        # 收入只算 income 的 1000
        self.assertEqual(float(resp.data['income']), 1000)
        # 支出只算 expense 的 200
        self.assertEqual(float(resp.data['expense']), 200)

    def test_dashboard_excludes_transfers(self):
        target = Account.objects.create(
            user=self.user, name='储蓄账户', account_type='bank', balance=0
        )
        Transaction.objects.create(
            user=self.user, transaction_type='transfer', amount=500,
            account=self.account, to_account=target, date=TODAY,
        )
        Transaction.objects.create(
            user=self.user, transaction_type='income', amount=3000,
            account=self.account, category=self.income_cat, date=TODAY,
        )

        resp = self.client.get('/api/transactions/dashboard/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(float(resp.data['month_income']), 3000)
        self.assertEqual(float(resp.data['month_expense']), 0)


class InvestmentAndBalanceSheetTest(IntegrationBaseTestCase):
    """投资持仓应出现在资产负债表中"""

    def setUp(self):
        super().setUp()
        self.asset_type = AssetType.objects.create(
            code='stock', name='股票', category='security', icon='📈',
        )
        self.invest_account = InvestmentAccount.objects.create(
            user=self.user, name='证券账户', asset_type=self.asset_type,
            balance=5000, currency='CNY',
        )
        self.holding = InvestmentHolding.objects.create(
            investment_account=self.invest_account,
            symbol='600519', name='贵州茅台',
            quantity=10, avg_cost=1800, current_price=1900,
            currency='CNY',
        )

    def test_investment_in_balance_sheet(self):
        resp = self.client.get('/api/reports/balance-sheet/')
        self.assertEqual(resp.status_code, 200)
        invest_items = resp.data['assets']['investments']['items']
        self.assertTrue(len(invest_items) > 0)
        # 市值 = 10 * 1900 = 19000
        self.assertEqual(float(resp.data['assets']['investments']['total']), 19000)

    def test_invest_account_balance_in_balance_sheet(self):
        resp = self.client.get('/api/reports/balance-sheet/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(float(resp.data['assets']['invest_balance']), 5000)

    def test_historical_balance_sheet_uses_snapshot(self):
        yesterday = TODAY - timedelta(days=1)
        # 创建昨天快照：市值 = 10 * 1700 = 17000
        DailyHoldingSnapshot.objects.create(
            holding=self.holding, user=self.user,
            symbol='600519', name='贵州茅台',
            date=yesterday,
            quantity=10, avg_cost=1800, close_price=1700,
            market_value=17000, cost_value=18000,
            daily_pl=-1000, total_pl=-1000,
            daily_pl_pct=Decimal('-5.56'), total_pl_pct=Decimal('-5.56'),
        )

        resp = self.client.get('/api/reports/balance-sheet/', {'date': str(yesterday)})
        self.assertEqual(resp.status_code, 200)
        # 应该使用快照市值 17000，而不是当前 19000
        self.assertEqual(float(resp.data['assets']['investments']['total']), 17000)


class LendingAndBalanceSheetTest(IntegrationBaseTestCase):
    """借贷记录应出现在资产负债表的应收/应付中"""

    def test_receivable_in_balance_sheet(self):
        LendingRecord.objects.create(
            user=self.user, record_type='lend', counterparty='张三',
            amount=5000, repaid_amount=2000, status='partial',
            date=TODAY - timedelta(days=30),
        )
        resp = self.client.get('/api/reports/balance-sheet/')
        self.assertEqual(resp.status_code, 200)
        recv = resp.data['assets']['receivables']
        self.assertEqual(len(recv['items']), 1)
        self.assertEqual(float(recv['total']), 3000)  # 5000 - 2000

    def test_payable_in_balance_sheet(self):
        LendingRecord.objects.create(
            user=self.user, record_type='borrow', counterparty='李四',
            amount=3000, repaid_amount=0, status='outstanding',
            date=TODAY - timedelta(days=30),
        )
        resp = self.client.get('/api/reports/balance-sheet/')
        self.assertEqual(resp.status_code, 200)
        pay = resp.data['liabilities']['payables']
        self.assertEqual(len(pay['items']), 1)
        self.assertEqual(float(pay['total']), 3000)

    def test_historical_balance_sheet_lending(self):
        """历史日期的应收应排除目标日期之后的还款"""
        record = LendingRecord.objects.create(
            user=self.user, record_type='lend', counterparty='王五',
            amount=10000, repaid_amount=6000, status='partial',
            date=TODAY - timedelta(days=60),
        )
        # 还款 1：30天前（在目标日期之前）
        yesterday = TODAY - timedelta(days=1)
        target = TODAY - timedelta(days=15)
        Repayment.objects.create(
            lending_record=record, repay_type='collect',
            amount=Decimal('2000'), interest=Decimal('0'),
            date=target - timedelta(days=5),
        )
        # 还款 2：昨天（在目标日期之后）
        Repayment.objects.create(
            lending_record=record, repay_type='collect',
            amount=Decimal('4000'), interest=Decimal('0'),
            date=yesterday,
        )

        resp = self.client.get('/api/reports/balance-sheet/', {'date': str(target)})
        self.assertEqual(resp.status_code, 200)
        recv = resp.data['assets']['receivables']
        # 历史日期：只算目标日期之前的还款 2000
        # 应收 = 10000 - 2000 = 8000
        self.assertEqual(float(recv['total']), 8000)


class BudgetAndTransactionTest(IntegrationBaseTestCase):
    """预算已花费金额应反映交易数据"""

    def test_budget_spent_reflects_transactions(self):
        budget = Budget.objects.create(
            user=self.user, category=self.category, amount=1000,
            period='monthly', year=TODAY.year, month=TODAY.month,
        )
        # 创建 3 笔支出
        self.create_transaction(amount=200, date=TODAY)
        self.create_transaction(amount=300, date=TODAY)
        self.create_transaction(amount=150, date=TODAY)

        resp = self.client.get('/api/budgets/')
        self.assertEqual(resp.status_code, 200)
        data = resp.data if isinstance(resp.data, list) else resp.data.get('results', resp.data)
        b = data[0] if isinstance(data, list) else data
        # 找到对应预算
        for item in (data if isinstance(data, list) else [data]):
            if item.get('category') == self.category.id or item.get('category_name'):
                b = item
                break
        self.assertEqual(float(b['spent']), 650)
        self.assertEqual(float(b['remaining']), 350)


class NetWorthHistoryWithSnapshotsTest(IntegrationBaseTestCase):
    """净资产历史应使用投资快照数据"""

    def setUp(self):
        super().setUp()
        self.asset_type = AssetType.objects.create(
            code='stock2', name='股票2', category='security', icon='📈',
        )
        self.invest_account = InvestmentAccount.objects.create(
            user=self.user, name='证券账户2', asset_type=self.asset_type,
            balance=2000, currency='CNY',
        )
        self.holding = InvestmentHolding.objects.create(
            investment_account=self.invest_account,
            symbol='000001', name='平安银行',
            quantity=100, avg_cost=15, current_price=16,
            currency='CNY',
        )

    def test_net_worth_uses_snapshot_when_available(self):
        """有快照的月份应使用快照市值而非当前市值"""
        last_month = TODAY - timedelta(days=35)
        month_key = last_month.strftime('%Y-%m')

        # 创建上月快照：市值 = 100 * 10 = 1000（远低于当前 1600）
        DailyHoldingSnapshot.objects.create(
            holding=self.holding, user=self.user,
            symbol='000001', name='平安银行',
            date=last_month,
            quantity=100, avg_cost=15, close_price=10,
            market_value=1000, cost_value=1500,
            daily_pl=Decimal('-500'), total_pl=Decimal('-500'),
            daily_pl_pct=Decimal('-33.33'), total_pl_pct=Decimal('-33.33'),
        )

        resp = self.client.get('/api/reports/net-worth-history/', {'months': 3})
        self.assertEqual(resp.status_code, 200)
        history = resp.data['history']

        # 找到上月数据
        month_data = next((h for h in history if h['month'] == month_key), None)
        self.assertIsNotNone(month_data)

        # 上月投资应使用快照 1000，而非当前 1600
        # 所以上月总资产应该比当前月少 600
        current_data = next(h for h in history if h['month'] == TODAY.strftime('%Y-%m'))
        diff = float(current_data['assets']) - float(month_data['assets'])
        # 差异应至少为 600（当前持仓1600 - 快照1000）
        self.assertGreater(diff, 500)
