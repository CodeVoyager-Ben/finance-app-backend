from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0011_populate_amounts'),
    ]

    operations = [
        migrations.CreateModel(
            name='DividendRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('symbol', models.CharField(max_length=30, verbose_name='代码')),
                ('name', models.CharField(max_length=50, verbose_name='名称')),
                ('dividend_type', models.CharField(choices=[('cash', '现金分红'), ('reinvest', '分红再投资'), ('interest', '利息收入')], max_length=10, verbose_name='分红方式')),
                ('ex_date', models.DateField(verbose_name='除权除息日')),
                ('pay_date', models.DateField(blank=True, null=True, verbose_name='发放日')),
                ('dividend_per_unit', models.DecimalField(decimal_places=4, max_digits=10, verbose_name='每单位分红')),
                ('quantity', models.DecimalField(decimal_places=4, max_digits=15, verbose_name='持有数量')),
                ('total_amount', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='总金额')),
                ('tax', models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name='扣税')),
                ('net_amount', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='税后净额')),
                ('note', models.CharField(blank=True, default='', max_length=200, verbose_name='备注')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('holding', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dividend_records', to='investments.investmentholding', verbose_name='持仓')),
                ('investment_account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dividend_records', to='investments.investmentaccount', verbose_name='投资账户')),
                ('transaction', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dividend_record', to='investments.investmenttransaction')),
            ],
            options={
                'verbose_name': '分红记录',
                'verbose_name_plural': '分红记录',
                'db_table': 'investment_dividend_records',
                'ordering': ['-ex_date', '-created_at'],
            },
        ),
    ]
