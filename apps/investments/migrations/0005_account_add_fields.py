from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0004_create_exchangerate'),
    ]

    operations = [
        migrations.AddField(
            model_name='investmentaccount',
            name='asset_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='accounts', to='investments.assettype', verbose_name='资产类型'),
        ),
        migrations.AddField(
            model_name='investmentaccount',
            name='currency',
            field=models.CharField(default='CNY', max_length=3, verbose_name='币种'),
        ),
        migrations.AlterField(
            model_name='investmentaccount',
            name='account_type',
            field=models.CharField(blank=True, choices=[('stock', '股票'), ('fund', '基金'), ('crypto', '虚拟货币'), ('futures', '期货')], max_length=20, null=True, verbose_name='投资类型(旧)'),
        ),
    ]
