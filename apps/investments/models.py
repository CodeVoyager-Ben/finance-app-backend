from datetime import date
from decimal import Decimal

from django.db import models
from django.conf import settings


class AssetType(models.Model):
    """资产类型（系统预设 + 用户自定义）"""
    CATEGORY_CHOICES = [
        ('security', '证券类'),
        ('commodity', '商品类'),
        ('fixed_income', '固收类'),
        ('real_estate', '房产类'),
        ('insurance', '保险类'),
        ('other', '其他'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='custom_asset_types',
        verbose_name='所属用户',
    )
    code = models.CharField('类型编码', max_length=30)
    name = models.CharField('类型名称', max_length=30)
    category = models.CharField('大类', max_length=20, choices=CATEGORY_CHOICES)
    icon = models.CharField('图标', max_length=10, blank=True, default='')
    color = models.CharField('颜色', max_length=7, blank=True, default='#1677ff')
    is_active = models.BooleanField('是否启用', default=True)
    sort_order = models.IntegerField('排序', default=0)

    class Meta:
        db_table = 'investment_asset_types'
        verbose_name = '资产类型'
        verbose_name_plural = verbose_name
        unique_together = [['user', 'code']]
        ordering = ['sort_order', 'id']

    def __str__(self):
        return self.name


class ExchangeRate(models.Model):
    """汇率快照"""
    base_currency = models.CharField('基准货币', max_length=3, default='CNY')
    target_currency = models.CharField('目标货币', max_length=3)
    rate = models.DecimalField('汇率', max_digits=12, decimal_places=6)
    rate_date = models.DateField('汇率日期')
    source = models.CharField('来源', max_length=30, blank=True, default='manual')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'investment_exchange_rates'
        verbose_name = '汇率'
        verbose_name_plural = verbose_name
        unique_together = [['base_currency', 'target_currency', 'rate_date']]
        ordering = ['-rate_date']

    def __str__(self):
        return f'{self.target_currency}/{self.base_currency}={self.rate}'


class InvestmentAccount(models.Model):
    """投资账户"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='investment_accounts',
    )
    name = models.CharField('账户名称', max_length=50)
    broker = models.CharField('券商/平台', max_length=50, blank=True, default='')
    account_type = models.CharField(
        '投资类型(旧)', max_length=20,
        choices=[
            ('stock', '股票'), ('fund', '基金'),
            ('crypto', '虚拟货币'), ('futures', '期货'),
        ],
        null=True, blank=True,
    )
    asset_type = models.ForeignKey(
        AssetType, on_delete=models.PROTECT,
        null=True, blank=True, related_name='accounts',
        verbose_name='资产类型',
    )
    fund_account = models.ForeignKey(
        'transactions.Account', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='investment_accounts',
        verbose_name='资金账户',
    )
    currency = models.CharField('币种', max_length=3, default='CNY')
    balance = models.DecimalField('账户余额', max_digits=15, decimal_places=2, default=0)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'investment_accounts'
        verbose_name = '投资账户'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        type_name = self.asset_type.name if self.asset_type else (self.account_type or '')
        return f'{self.name} ({type_name})'


class InvestmentHolding(models.Model):
    """投资持仓"""
    investment_account = models.ForeignKey(
        InvestmentAccount, on_delete=models.CASCADE,
        related_name='holdings', verbose_name='投资账户',
    )
    symbol = models.CharField('代码', max_length=30)
    name = models.CharField('名称', max_length=50)
    quantity = models.DecimalField('持有数量', max_digits=15, decimal_places=4, default=0)
    avg_cost = models.DecimalField('平均成本', max_digits=15, decimal_places=4, default=0)
    current_price = models.DecimalField('当前价格', max_digits=15, decimal_places=4, default=0)
    first_buy_date = models.DateField('首次买入日期', null=True, blank=True)
    previous_close_price = models.DecimalField(
        '昨收价', max_digits=15, decimal_places=4, default=0,
    )
    accumulated_dividend = models.DecimalField(
        '累计分红/利息', max_digits=15, decimal_places=2, default=0,
    )
    group_tag = models.CharField('自定义分组', max_length=50, blank=True, default='')
    currency = models.CharField('币种', max_length=3, blank=True, default='')
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'investment_holdings'
        verbose_name = '投资持仓'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.name}({self.symbol})'

    @property
    def effective_currency(self):
        return self.currency or self.investment_account.currency

    @property
    def market_value(self):
        return self.quantity * self.current_price

    @property
    def cost_value(self):
        return self.quantity * self.avg_cost

    @property
    def profit_loss(self):
        return self.market_value - self.cost_value

    @property
    def profit_loss_pct(self):
        if self.cost_value == 0:
            return Decimal('0')
        return (self.profit_loss / self.cost_value) * 100

    @property
    def holding_days(self):
        if self.first_buy_date:
            return (date.today() - self.first_buy_date).days
        return 0

    @property
    def daily_profit_loss(self):
        if self.previous_close_price == 0:
            return Decimal('0')
        return (self.current_price - self.previous_close_price) * self.quantity

    @property
    def daily_profit_loss_pct(self):
        if self.previous_close_price == 0:
            return Decimal('0')
        return ((self.current_price - self.previous_close_price) / self.previous_close_price) * 100

    @property
    def total_return_rate(self):
        if self.cost_value == 0:
            return Decimal('0')
        return ((self.market_value + self.accumulated_dividend - self.cost_value) / self.cost_value) * 100

    @property
    def annualized_return(self):
        days = self.holding_days
        if days <= 0 or self.cost_value == 0:
            return Decimal('0')
        total_value = self.market_value + self.accumulated_dividend
        if total_value <= 0:
            return Decimal('0')
        try:
            return ((total_value / self.cost_value) ** (Decimal('365') / days) - 1) * 100
        except Exception:
            return Decimal('0')

    @property
    def daily_avg_cost(self):
        days = self.holding_days
        if days == 0:
            return Decimal('0')
        return self.cost_value / days


class InvestmentTransaction(models.Model):
    """投资交易记录"""
    TYPE_CHOICES = [
        ('buy', '买入'),
        ('sell', '卖出'),
        ('dividend', '分红'),
        ('interest', '利息'),
        ('dividend_reinvest', '分红再投资'),
        ('deposit', '入金'),
        ('withdraw', '出金'),
        ('fee', '费用'),
        ('split', '拆股/合股'),
    ]

    investment_account = models.ForeignKey(
        InvestmentAccount, on_delete=models.CASCADE,
        related_name='transactions', verbose_name='投资账户',
    )
    holding = models.ForeignKey(
        InvestmentHolding, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions', verbose_name='持仓',
    )
    symbol = models.CharField('代码', max_length=30)
    name = models.CharField('名称', max_length=50)
    transaction_type = models.CharField('交易类型', max_length=20, choices=TYPE_CHOICES)
    quantity = models.DecimalField('数量', max_digits=15, decimal_places=4, default=0)
    price = models.DecimalField('价格', max_digits=15, decimal_places=4, default=0)
    amount = models.DecimalField('交易金额', max_digits=15, decimal_places=2, default=0)
    fee = models.DecimalField('手续费', max_digits=10, decimal_places=2, default=0)
    profit_loss = models.DecimalField('盈亏金额', max_digits=15, decimal_places=2, default=0)
    dividend_per_unit = models.DecimalField('每单位分红', max_digits=10, decimal_places=4, default=0)
    related_transaction = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='related_transactions',
    )
    date = models.DateField('交易日期')
    note = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'investment_transactions'
        verbose_name = '投资交易'
        verbose_name_plural = verbose_name
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.date} {self.get_transaction_type_display()} {self.symbol}'


class DailyHoldingSnapshot(models.Model):
    """每日持仓快照（收盘后自动生成）"""
    holding = models.ForeignKey(
        InvestmentHolding, on_delete=models.CASCADE,
        related_name='daily_snapshots', verbose_name='持仓',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='holding_snapshots', verbose_name='用户',
    )
    symbol = models.CharField('代码', max_length=30)
    name = models.CharField('名称', max_length=50)
    date = models.DateField('日期')
    quantity = models.DecimalField('数量', max_digits=15, decimal_places=4)
    avg_cost = models.DecimalField('成本价', max_digits=15, decimal_places=4)
    close_price = models.DecimalField('收盘价', max_digits=15, decimal_places=4)
    previous_close = models.DecimalField('昨收价', max_digits=15, decimal_places=4, default=0)
    market_value = models.DecimalField('市值', max_digits=15, decimal_places=2)
    cost_value = models.DecimalField('成本', max_digits=15, decimal_places=2)
    daily_pl = models.DecimalField('当日盈亏', max_digits=15, decimal_places=2)
    total_pl = models.DecimalField('累计盈亏', max_digits=15, decimal_places=2)
    daily_pl_pct = models.DecimalField('当日盈亏%', max_digits=8, decimal_places=2, default=0)
    total_pl_pct = models.DecimalField('累计盈亏%', max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'investment_daily_snapshots'
        verbose_name = '每日持仓快照'
        verbose_name_plural = verbose_name
        unique_together = [['holding', 'date']]
        ordering = ['-date']

    def __str__(self):
        return f'{self.date} {self.symbol} 日盈亏={self.daily_pl}'


class DividendRecord(models.Model):
    """分红/利息记录"""
    DIVIDEND_TYPE_CHOICES = [
        ('cash', '现金分红'),
        ('reinvest', '分红再投资'),
        ('interest', '利息收入'),
    ]

    investment_account = models.ForeignKey(
        InvestmentAccount, on_delete=models.CASCADE,
        related_name='dividend_records', verbose_name='投资账户',
    )
    holding = models.ForeignKey(
        InvestmentHolding, on_delete=models.SET_NULL,
        null=True, related_name='dividend_records', verbose_name='持仓',
    )
    symbol = models.CharField('代码', max_length=30)
    name = models.CharField('名称', max_length=50)
    dividend_type = models.CharField('分红方式', max_length=10, choices=DIVIDEND_TYPE_CHOICES)
    ex_date = models.DateField('除权除息日')
    pay_date = models.DateField('发放日', null=True, blank=True)
    dividend_per_unit = models.DecimalField('每单位分红', max_digits=10, decimal_places=4)
    quantity = models.DecimalField('持有数量', max_digits=15, decimal_places=4)
    total_amount = models.DecimalField('总金额', max_digits=15, decimal_places=2)
    tax = models.DecimalField('扣税', max_digits=10, decimal_places=2, default=0)
    net_amount = models.DecimalField('税后净额', max_digits=15, decimal_places=2)
    transaction = models.OneToOneField(
        InvestmentTransaction, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dividend_record',
    )
    note = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'investment_dividend_records'
        verbose_name = '分红记录'
        verbose_name_plural = verbose_name
        ordering = ['-ex_date', '-created_at']

    def __str__(self):
        return f'{self.ex_date} {self.symbol} {self.get_dividend_type_display()}'
