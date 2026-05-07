import logging
from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.investments.models import InvestmentHolding, DailyHoldingSnapshot
from apps.investments.stock_data import fetch_batch_prices
from apps.investments.fee_calculator import calculate_buy_fees, calculate_sell_fees

logger = logging.getLogger(__name__)

# A 股休市节假日（2025-2026 年主要节假日，可按需补充）
HOLIDAYS = {
    # 2025
    date(2025, 1, 1),   # 元旦
    date(2025, 1, 28), date(2025, 1, 29), date(2025, 1, 30), date(2025, 1, 31),
    date(2025, 2, 3), date(2025, 2, 4),  # 春节
    date(2025, 4, 4), date(2025, 4, 5),  # 清明
    date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3), date(2025, 5, 4), date(2025, 5, 5),  # 劳动节
    date(2025, 5, 31), date(2025, 6, 1), date(2025, 6, 2),  # 端午
    date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3),
    date(2025, 10, 4), date(2025, 10, 5), date(2025, 10, 6),
    date(2025, 10, 7), date(2025, 10, 8),  # 国庆
    # 2026
    date(2026, 1, 1), date(2026, 1, 2),  # 元旦
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18),
    date(2026, 2, 19), date(2026, 2, 20),  # 春节
    date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 6),  # 清明
    date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3),
    date(2026, 5, 4), date(2026, 5, 5),  # 劳动节
    date(2026, 5, 30), date(2026, 5, 31), date(2026, 6, 1),  # 端午
    date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3),
    date(2026, 10, 4), date(2026, 10, 5), date(2026, 10, 6),
    date(2026, 10, 7),  # 国庆
}


def is_trading_day(d=None):
    """判断是否为 A 股交易日（工作日 + 非节假日）"""
    if d is None:
        d = date.today()
    if d.weekday() >= 5:
        return False
    if d in HOLIDAYS:
        return False
    return True


def run_price_update(user_id=None, dry_run=False):
    """
    核心逻辑：获取价格、更新持仓、保存每日快照。
    返回 (updated_count, total_count, failed_symbols)。
    """
    today = date.today()
    holdings = InvestmentHolding.objects.filter(
        quantity__gt=0,
        investment_account__asset_type__category='security',
    ).select_related('investment_account', 'investment_account__user')

    if user_id:
        holdings = holdings.filter(investment_account__user_id=user_id)

    stock_holdings = [h for h in holdings if h.symbol.isdigit() and len(h.symbol) == 6]

    if not stock_holdings:
        return 0, 0, []

    symbols = list(set(h.symbol for h in stock_holdings))
    price_map = fetch_batch_prices(symbols)

    updated = 0
    failed = []
    for holding in stock_holdings:
        price_info = price_map.get(holding.symbol)
        if not price_info or not price_info.get('current_price'):
            failed.append(holding.symbol)
            continue

        new_price = Decimal(str(price_info['current_price']))
        new_prev_close = Decimal(str(price_info.get('previous_close') or holding.current_price))

        if dry_run:
            logger.info(f'  {holding.symbol} {holding.name}: {holding.current_price} -> {new_price}')
            updated += 1
            continue

        # 保存快照（用更新前的数据计算当日盈亏）
        old_price = holding.current_price
        daily_pl = (new_price - (new_prev_close or old_price)) * holding.quantity
        daily_pl_pct = ((new_price - (new_prev_close or old_price)) / (new_prev_close or old_price) * 100) if (new_prev_close or old_price) > 0 else Decimal('0')
        market_value = new_price * holding.quantity
        cost_value = holding.avg_cost * holding.quantity
        total_pl = market_value - cost_value
        total_pl_pct = (total_pl / cost_value * 100) if cost_value > 0 else Decimal('0')

        DailyHoldingSnapshot.objects.update_or_create(
            holding=holding,
            date=today,
            defaults={
                'user': holding.investment_account.user,
                'symbol': holding.symbol,
                'name': holding.name,
                'quantity': holding.quantity,
                'avg_cost': holding.avg_cost,
                'close_price': new_price,
                'previous_close': new_prev_close or old_price,
                'market_value': market_value.quantize(Decimal('0.01')),
                'cost_value': cost_value.quantize(Decimal('0.01')),
                'daily_pl': daily_pl.quantize(Decimal('0.01')),
                'total_pl': total_pl.quantize(Decimal('0.01')),
                'daily_pl_pct': daily_pl_pct.quantize(Decimal('0.01')),
                'total_pl_pct': total_pl_pct.quantize(Decimal('0.01')),
            },
        )

        # 更新持仓价格
        holding.previous_close_price = new_prev_close or holding.current_price
        holding.current_price = new_price
        holding.save(update_fields=['previous_close_price', 'current_price', 'updated_at'])
        updated += 1

    return updated, len(stock_holdings), list(set(failed))


class Command(BaseCommand):
    help = '自动获取 A 股最新价格，更新持仓，保存每日快照'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', type=int, help='只更新指定用户')
        parser.add_argument('--dry-run', action='store_true', help='只显示不保存')
        parser.add_argument('--force', action='store_true', help='强制执行（忽略交易日检查）')

    def handle(self, *args, **options):
        today = date.today()
        if not options['force'] and not is_trading_day(today):
            self.stdout.write(f'{today} 非交易日（周末或节假日），跳过。使用 --force 强制执行。')
            return

        now = datetime.now().strftime('%H:%M')
        self.stdout.write(f'[{now}] 开始更新持仓价格...')

        updated, total, failed = run_price_update(
            user_id=options.get('user_id'),
            dry_run=options.get('dry_run', False),
        )

        msg = f'完成: {updated}/{total} 个持仓已更新'
        if failed:
            msg += f'，{len(failed)} 个失败: {", ".join(failed)}'
        self.stdout.write(self.style.SUCCESS(msg))
