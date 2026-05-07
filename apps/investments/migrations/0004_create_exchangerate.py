from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0003_create_assettype'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExchangeRate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('base_currency', models.CharField(default='CNY', max_length=3, verbose_name='基准货币')),
                ('target_currency', models.CharField(max_length=3, verbose_name='目标货币')),
                ('rate', models.DecimalField(decimal_places=6, max_digits=12, verbose_name='汇率')),
                ('rate_date', models.DateField(verbose_name='汇率日期')),
                ('source', models.CharField(blank=True, default='manual', max_length=30, verbose_name='来源')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '汇率',
                'verbose_name_plural': '汇率',
                'db_table': 'investment_exchange_rates',
                'ordering': ['-rate_date'],
                'unique_together': {('base_currency', 'target_currency', 'rate_date')},
            },
        ),
    ]
