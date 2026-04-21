from django.db import models
from django.conf import settings


class LendingRecord(models.Model):
    """借贷记录"""
    TYPE_CHOICES = [
        ('lend', '借出'),
        ('borrow', '借入'),
    ]
    STATUS_CHOICES = [
        ('outstanding', '未还清'),
        ('partial', '部分归还'),
        ('settled', '已结清'),
        ('written_off', '已核销'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lending_records')
    record_type = models.CharField('类型', max_length=10, choices=TYPE_CHOICES)
    counterparty = models.CharField('对方姓名', max_length=50)
    amount = models.DecimalField('金额', max_digits=15, decimal_places=2)
    repaid_amount = models.DecimalField('已还金额', max_digits=15, decimal_places=2, default=0)
    interest_amount = models.DecimalField('利息', max_digits=15, decimal_places=2, default=0)
    account = models.ForeignKey(
        'transactions.Account', on_delete=models.SET_NULL, null=True,
        related_name='lending_records', verbose_name='关联账户',
    )
    status = models.CharField('状态', max_length=15, choices=STATUS_CHOICES, default='outstanding')
    date = models.DateField('日期')
    expected_return_date = models.DateField('预计归还日期', null=True, blank=True)
    reason = models.CharField('事由', max_length=200, blank=True, default='')
    note = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        db_table = 'lending_records'
        verbose_name = '借贷记录'
        verbose_name_plural = verbose_name
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.get_record_type_display()} {self.counterparty} ¥{self.amount}'

    @property
    def remaining_amount(self):
        """剩余未还金额"""
        return self.amount - self.repaid_amount


class Repayment(models.Model):
    """还款记录"""
    REPAY_TYPE_CHOICES = [
        ('collect', '收款'),
        ('repay', '还款'),
    ]

    lending_record = models.ForeignKey(LendingRecord, on_delete=models.CASCADE, related_name='repayments', verbose_name='借贷记录')
    repay_type = models.CharField('还款类型', max_length=10, choices=REPAY_TYPE_CHOICES)
    amount = models.DecimalField('还款金额', max_digits=15, decimal_places=2)
    interest = models.DecimalField('其中利息', max_digits=15, decimal_places=2, default=0)
    account = models.ForeignKey(
        'transactions.Account', on_delete=models.SET_NULL, null=True,
        related_name='repayments', verbose_name='还款账户',
    )
    date = models.DateField('还款日期')
    note = models.CharField('备注', max_length=200, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        db_table = 'repayments'
        verbose_name = '还款记录'
        verbose_name_plural = verbose_name
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f'{self.get_repay_type_display()} ¥{self.amount} on {self.date}'
