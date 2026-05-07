from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum, Q
from apps.transactions.models import Account, Transaction


class Command(BaseCommand):
    help = '从交易流水重算所有账户余额，修复因 stale cache bug 导致的余额错误'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='仅预览，不写入数据库')
        parser.add_argument('--user-id', type=int, help='仅修复指定用户')
        parser.add_argument('--account-id', type=int, help='仅修复指定账户')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        filters = {}
        if options['user_id']:
            filters['user_id'] = options['user_id']
        if options['account_id']:
            filters['id'] = options['account_id']

        accounts = Account.objects.filter(**filters).order_by('user_id', 'id')
        fixed = 0

        for acc in accounts:
            income = Transaction.objects.filter(
                account=acc, transaction_type='income',
            ).aggregate(s=Sum('amount', default=0))['s']

            expense = Transaction.objects.filter(
                account=acc, transaction_type='expense',
            ).aggregate(s=Sum('amount', default=0))['s']

            transfer_out = Transaction.objects.filter(
                account=acc, transaction_type='transfer',
            ).aggregate(s=Sum('amount', default=0))['s']

            transfer_in = Transaction.objects.filter(
                to_account=acc, transaction_type='transfer',
            ).aggregate(s=Sum('amount', default=0))['s']

            txn_count = Transaction.objects.filter(Q(account=acc) | Q(to_account=acc)).count()
            calculated = income - expense - transfer_out + transfer_in
            diff = acc.balance - calculated

            if abs(diff) < Decimal('0.01'):
                self.stdout.write(f'✓ Account id={acc.id} user={acc.user_id} [{acc.name}] balance={acc.balance} (correct)')
                continue

            if txn_count == 0:
                self.stdout.write(
                    self.style.WARNING(
                        f'⊘ Account id={acc.id} user={acc.user_id} [{acc.name}] '
                        f'balance={acc.balance} (no transactions, likely manual — skipped)'
                    )
                )
                continue

            self.stdout.write(
                f'❌ Account id={acc.id} user={acc.user_id} [{acc.name}] '
                f'current={acc.balance} → correct={calculated} (diff={diff})'
            )

            if not dry_run:
                acc.balance = calculated
                acc.save(update_fields=['balance'])
                fixed += 1

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run — no changes written.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\nDone. Fixed {fixed} accounts.'))
