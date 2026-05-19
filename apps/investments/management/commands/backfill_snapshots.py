import json
import logging
from datetime import date, timedelta
from decimal import Decimal

import requests
from django.core.management.base import BaseCommand

from apps.investments.models import DailyHoldingSnapshot, InvestmentHolding

logger = logging.getLogger(__name__)

SINA_KLINE_URL = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'


def _symbol_to_sina(symbol):
    if not symbol or not symbol.isdigit() or len(symbol) != 6:
        return None
    return f'sh{symbol}' if symbol[0] == '6' else f'sz{symbol}'


def _fetch_klines(symbol, start_date, end_date):
    """通过新浪财经获取历史 K 线数据"""
    sina_code = _symbol_to_sina(symbol)
    if not sina_code:
        return {}

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days = (end - start).days + 5
    try:
        resp = requests.get(SINA_KLINE_URL, params={
            'symbol': sina_code, 'scale': '240', 'ma': 'no', 'datalen': str(days),
        }, timeout=10)
        if resp.status_code != 200:
            return {}
        items = json.loads(resp.text)
        result = {}
        for item in items:
            day = item['day']
            if start_date <= day <= end_date:
                result[day] = {
                    'open': Decimal(item['open']),
                    'close': Decimal(item['close']),
                    'high': Decimal(item['high']),
                    'low': Decimal(item['low']),
                }
        return result
    except Exception as e:
        logger.error(f'获取 {symbol} K线失败: {e}')
        return {}


class Command(BaseCommand):
    help = '回补缺失日期的持仓快照数据'

    def add_arguments(self, parser):
        parser.add_argument('--start-date', type=str, required=True, help='起始日期 YYYY-MM-DD')
        parser.add_argument('--end-date', type=str, required=True, help='结束日期 YYYY-MM-DD')
        parser.add_argument('--user-id', type=int, default=None, help='指定用户ID')
        parser.add_argument('--dry-run', action='store_true', help='仅预览')

    def handle(self, *args, **options):
        start = options['start_date']
        end = options['end_date']
        dry_run = options['dry_run']

        holdings = InvestmentHolding.objects.filter(quantity__gt=0)
        if options['user_id']:
            holdings = holdings.filter(investment_account__user_id=options['user_id'])

        stock_holdings = [h for h in holdings if h.symbol.isdigit() and len(h.symbol) == 6]
        if not stock_holdings:
            self.stdout.write('没有需要处理的持仓')
            return

        symbols = list(set(h.symbol for h in stock_holdings))
        self.stdout.write(f'持仓代码: {symbols}')

        kline_cache = {}
        for symbol in symbols:
            self.stdout.write(f'获取 {symbol} K线 ({start} ~ {end})...')
            kline_cache[symbol] = _fetch_klines(symbol, start, end)

        # Get sorted trading dates in range (filter non-trading days)
        from apps.investments.management.commands.update_stock_prices import is_trading_day
        all_dates = set()
        for klines in kline_cache.values():
            all_dates.update(klines.keys())
        trading_dates = sorted(
            d for d in all_dates
            if start <= d <= end and is_trading_day(date.fromisoformat(d))
        )

        created = 0
        skipped = 0
        for holding in stock_holdings:
            symbol = holding.symbol
            klines = kline_cache.get(symbol, {})

            for td in trading_dates:
                if DailyHoldingSnapshot.objects.filter(holding=holding, date=td).exists():
                    skipped += 1
                    continue

                kline = klines.get(td)
                if not kline:
                    continue

                prev_dates = [d for d in sorted(klines.keys()) if d < td]
                prev_close = klines[prev_dates[-1]]['close'] if prev_dates else kline['open']

                close_price = kline['close']
                market_value = close_price * holding.quantity
                cost_value = holding.avg_cost * holding.quantity
                total_pl = market_value - cost_value
                total_pl_pct = (total_pl / cost_value * 100) if cost_value > 0 else Decimal('0')
                daily_pl = (close_price - prev_close) * holding.quantity
                daily_pl_pct = ((close_price - prev_close) / prev_close * 100) if prev_close > 0 else Decimal('0')

                if dry_run:
                    self.stdout.write(
                        f'  [DRY] {td} {symbol} close={close_price} prev={prev_close} '
                        f'dpl={daily_pl} tpl={total_pl}'
                    )
                else:
                    DailyHoldingSnapshot.objects.create(
                        holding=holding,
                        user=holding.investment_account.user,
                        symbol=symbol,
                        name=holding.name,
                        date=td,
                        quantity=holding.quantity,
                        avg_cost=holding.avg_cost,
                        close_price=close_price,
                        previous_close=prev_close,
                        market_value=market_value.quantize(Decimal('0.01')),
                        cost_value=cost_value.quantize(Decimal('0.01')),
                        daily_pl=daily_pl.quantize(Decimal('0.01')),
                        total_pl=total_pl.quantize(Decimal('0.01')),
                        daily_pl_pct=daily_pl_pct.quantize(Decimal('0.01')),
                        total_pl_pct=total_pl_pct.quantize(Decimal('0.01')),
                    )
                created += 1

        action = 'Would create' if dry_run else 'Created'
        self.stdout.write(self.style.SUCCESS(f'{action} {created} snapshots, skipped {skipped} existing'))
