import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AssetType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=30, verbose_name='类型编码')),
                ('name', models.CharField(max_length=30, verbose_name='类型名称')),
                ('category', models.CharField(choices=[('security', '证券类'), ('commodity', '商品类'), ('fixed_income', '固收类'), ('real_estate', '房产类'), ('insurance', '保险类'), ('other', '其他')], max_length=20, verbose_name='大类')),
                ('icon', models.CharField(blank=True, default='', max_length=10, verbose_name='图标')),
                ('color', models.CharField(blank=True, default='#1677ff', max_length=7, verbose_name='颜色')),
                ('is_active', models.BooleanField(default=True, verbose_name='是否启用')),
                ('sort_order', models.IntegerField(default=0, verbose_name='排序')),
                ('user', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='custom_asset_types', to=settings.AUTH_USER_MODEL, verbose_name='所属用户')),
            ],
            options={
                'verbose_name': '资产类型',
                'verbose_name_plural': '资产类型',
                'db_table': 'investment_asset_types',
                'ordering': ['sort_order', 'id'],
                'unique_together': {('user', 'code')},
            },
        ),
    ]
