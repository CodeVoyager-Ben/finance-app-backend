from django.db import migrations


PRESETS = [
    ('stock', '股票', 'security', '📈', '#1677ff', 1),
    ('fund', '基金', 'security', '📊', '#52c41a', 2),
    ('crypto', '虚拟货币', 'other', '🪙', '#faad14', 3),
    ('futures', '期货', 'other', '📉', '#722ed1', 4),
    ('bond', '债券', 'fixed_income', '📜', '#13c2c2', 5),
    ('gold', '黄金', 'commodity', '🥇', '#ffc53d', 6),
    ('real_estate', '房产', 'real_estate', '🏠', '#eb2f96', 7),
    ('fixed_deposit', '定期存款', 'fixed_income', '🏦', '#597ef7', 8),
    ('insurance', '保险', 'insurance', '🛡️', '#95de64', 9),
]


def load_asset_types_and_migrate_accounts(apps, schema_editor):
    AssetType = apps.get_model('investments', 'AssetType')
    InvestmentAccount = apps.get_model('investments', 'InvestmentAccount')

    type_map = {}
    for code, name, category, icon, color, sort_order in PRESETS:
        at = AssetType.objects.create(
            user=None, code=code, name=name,
            category=category, icon=icon, color=color,
            is_active=True, sort_order=sort_order,
        )
        type_map[code] = at.id

    for acc in InvestmentAccount.objects.all():
        if acc.account_type in type_map:
            acc.asset_type_id = type_map[acc.account_type]
            acc.currency = 'CNY'
            acc.save(update_fields=['asset_type_id', 'currency'])


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0005_account_add_fields'),
    ]

    operations = [
        migrations.RunPython(load_asset_types_and_migrate_accounts, reverse_func),
    ]
