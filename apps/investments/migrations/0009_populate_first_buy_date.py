from django.db import migrations


def populate_first_buy_date(apps, schema_editor):
    Holding = apps.get_model('investments', 'InvestmentHolding')
    Transaction = apps.get_model('investments', 'InvestmentTransaction')

    for h in Holding.objects.all():
        earliest = Transaction.objects.filter(
            investment_account=h.investment_account,
            symbol=h.symbol,
            transaction_type='buy',
        ).order_by('date').first()
        if earliest:
            h.first_buy_date = earliest.date
            h.save(update_fields=['first_buy_date'])


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0008_holding_add_fields'),
    ]

    operations = [
        migrations.RunPython(populate_first_buy_date, reverse_func),
    ]
