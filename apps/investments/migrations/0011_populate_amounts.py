from django.db import migrations


def populate_amounts(apps, schema_editor):
    Transaction = apps.get_model('investments', 'InvestmentTransaction')
    for t in Transaction.objects.all():
        t.amount = t.quantity * t.price
        t.save(update_fields=['amount'])


def reverse_func(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('investments', '0010_transaction_expand'),
    ]

    operations = [
        migrations.RunPython(populate_amounts, reverse_func),
    ]
