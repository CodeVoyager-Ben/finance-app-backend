from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0006_migrate_asset_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='investmentholding',
            name='accumulated_dividend',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=2, verbose_name='累计分红/利息'),
        ),
        migrations.AddField(
            model_name='investmentholding',
            name='currency',
            field=models.CharField(blank=True, default='', max_length=3, verbose_name='币种'),
        ),
        migrations.AddField(
            model_name='investmentholding',
            name='first_buy_date',
            field=models.DateField(blank=True, null=True, verbose_name='首次买入日期'),
        ),
        migrations.AddField(
            model_name='investmentholding',
            name='group_tag',
            field=models.CharField(blank=True, default='', max_length=50, verbose_name='自定义分组'),
        ),
        migrations.AddField(
            model_name='investmentholding',
            name='previous_close_price',
            field=models.DecimalField(default=0, max_digits=15, decimal_places=4, verbose_name='昨收价'),
        ),
    ]
