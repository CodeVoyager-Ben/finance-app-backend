from django.db import models
from django.conf import settings


class Account(models.Model):
    """资金账户"""
    TYPE_CHOICES = [
        ('cash', '现金'),
        ('bank', '银行卡'),
        ('credit_card', '信用卡'),
        ('alipay', '支付宝'),
        ('wechat', '微信'),
        ('other', '其他'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='accounts')
    name = models.CharField('账户名称', max_length=50)
    account_type = models.CharField('账户类型', max_length=20, choices=TYPE_CHOICES, default='cash')
    balance = models.DecimalField('余额', max_digits=15, decimal_places=2, default=0)
    icon = models.CharField('图标', max_length=50, blank=True, default='')
    color = models.CharField('颜色', max_length=20, blank=True, default='#1677ff')
    is_active = models.BooleanField('是否启用', default=True)
    exclude_from_reports = models.BooleanField('排除报表统计', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'accounts'

    class Meta:
        db_table = 'accounts'
        verbose_name = '账户'
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_account_type_display()})'


class Category(models.Model):
    """收支分类"""
    TYPE_CHOICES = [
        ('income', '收入'),
        ('expense', '支出'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField('分类名称', max_length=50)
    category_type = models.CharField('分类类型', max_length=10, choices=TYPE_CHOICES)
    icon = models.CharField('图标', max_length=50, blank=True, default='')
    color = models.CharField('颜色', max_length=20, blank=True, default='')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children', verbose_name='父分类')
    sort_order = models.IntegerField('排序', default=0)
    is_active = models.BooleanField('是否启用', default=True)

    class Meta:
        db_table = 'categories'
        verbose_name = '分类'
        verbose_name_plural = verbose_name
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f'{self.name} ({self.get_category_type_display()})'


class Transaction(models.Model):
    """收支流水"""
    TYPE_CHOICES = [
        ('income', '收入'),
        ('expense', '支出'),
        ('transfer', '转账'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='transactions', verbose_name='账户')
    to_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='incoming_transfers', verbose_name='转入账户')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='transactions', verbose_name='分类')
    transaction_type = models.CharField('类型', max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField('金额', max_digits=15, decimal_places=2)
    note = models.CharField('备注', max_length=200, blank=True, default='')
    date = models.DateField('日期')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'transactions'
        verbose_name = '收支流水'
        verbose_name_plural = verbose_name
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.date} {self.get_transaction_type_display()} {self.amount}'


class Budget(models.Model):
    """预算"""
    PERIOD_CHOICES = [
        ('monthly', '月度'),
        ('yearly', '年度'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='budgets')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='budgets', verbose_name='分类（空=总预算）')
    amount = models.DecimalField('预算金额', max_digits=15, decimal_places=2)
    period = models.CharField('周期', max_length=10, choices=PERIOD_CHOICES, default='monthly')
    year = models.IntegerField('年份', default=0)
    month = models.IntegerField('月份', default=0)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'budgets'
        verbose_name = '预算'
        verbose_name_plural = verbose_name
        ordering = ['-period', 'category']

    def __str__(self):
        name = self.category.name if self.category else '总预算'
        return f'{name} {self.get_period_display()} ¥{self.amount}'
