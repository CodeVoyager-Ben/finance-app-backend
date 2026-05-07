from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0009_populate_first_buy_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='investmenttransaction',
            name='transaction_type',
            field=models.CharField(choices=[('buy', '买入'), ('sell', '卖出'), ('dividend', '分红'), ('interest', '利息'), ('dividend_reinvest', '分红再投资'), ('deposit', '入金'), ('withdraw', '出金'), ('fee', '费用'), ('split', '拆股/合股')], max_length=20, verbose_name='交易类型'),
        ),
        migrations.AlterField(
            model_name='investmenttransaction',
            name='price',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=15, verbose_name='价格'),
        ),
        migrations.AlterField(
            model_name='investmenttransaction',
            name='quantity',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=15, verbose_name='数量'),
        ),
        migrations.AddField(
            model_name='investmenttransaction',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='交易金额'),
        ),
        migrations.AddField(
            model_name='investmenttransaction',
            name='dividend_per_unit',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=10, verbose_name='每单位分红'),
        ),
        migrations.AddField(
            model_name='investmenttransaction',
            name='related_transaction',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='related_transactions', to='investments.investmenttransaction'),
        ),
    ]
