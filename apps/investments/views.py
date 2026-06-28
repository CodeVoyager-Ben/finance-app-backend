from decimal import Decimal

from django.db import models as db_models, transaction as db_transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    AssetType, ExchangeRate,
    InvestmentAccount, InvestmentHolding, InvestmentTransaction,
    DividendRecord, DailyHoldingSnapshot,
)
from .serializers import (
    AssetTypeSerializer,
    ExchangeRateSerializer,
    InvestmentAccountSerializer,
    InvestmentHoldingSerializer, InvestmentHoldingUpdateSerializer,
    InvestmentTransactionSerializer, InvestmentTransactionCreateSerializer,
    InvestmentDashboardSerializer,
    DividendRecordSerializer, DividendRecordCreateSerializer,
    DailyHoldingSnapshotSerializer,
)
from .services import update_holding_from_transaction, handle_dividend, to_cny
from .stock_data import search_security


# ─── AssetType ────────────────────────────────────────────────

class AssetTypeViewSet(viewsets.ModelViewSet):
    serializer_class = AssetTypeSerializer

    def get_queryset(self):
        return AssetType.objects.filter(
            db_models.Q(user=None) | db_models.Q(user=self.request.user)
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.user is None:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('系统预设类型不可修改')
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user is None:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('系统预设类型不可删除')
        instance.delete()


# ─── ExchangeRate ──────────────────────────────────────────────

class ExchangeRateViewSet(viewsets.ModelViewSet):
    serializer_class = ExchangeRateSerializer
    filterset_fields = ['target_currency', 'rate_date']
    ordering_fields = ['rate_date']

    def get_queryset(self):
        return ExchangeRate.objects.all()

    @action(detail=False, methods=['get'])
    def latest(self, request):
        currencies = ExchangeRate.objects.values_list(
            'target_currency', flat=True
        ).distinct()
        rates = []
        for c in currencies:
            obj = ExchangeRate.objects.filter(target_currency=c).order_by('-rate_date').first()
            if obj:
                rates.append(ExchangeRateSerializer(obj).data)
        return Response(rates)


# ─── InvestmentAccount ─────────────────────────────────────────

class InvestmentAccountViewSet(viewsets.ModelViewSet):
    serializer_class = InvestmentAccountSerializer
    filterset_fields = ['asset_type', 'currency', 'is_active']

    def get_queryset(self):
        return InvestmentAccount.objects.filter(
            user=self.request.user
        ).select_related('asset_type', 'fund_account').prefetch_related('holdings')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        from datetime import date as date_type
        instance = serializer.instance
        old_balance = instance.balance
        new_balance = serializer.validated_data.pop('balance', None)
        with db_transaction.atomic():
            instance = serializer.save()
            if new_balance is not None and new_balance != old_balance:
                diff = new_balance - old_balance
                tx = InvestmentTransaction.objects.create(
                    investment_account=instance,
                    symbol='CASH',
                    name='余额调整',
                    transaction_type='deposit' if diff > 0 else 'withdraw',
                    amount=abs(diff),
                    date=date_type.today(),
                    note='余额调整',
                )
                update_holding_from_transaction(tx)
                instance.refresh_from_db(fields=['balance'])

    @action(detail=False, methods=['get'], url_path='security-lookup')
    def security_lookup(self, request):
        q = request.query_params.get('q', '').strip()
        results = search_security(q)
        return Response(results)

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        account = self.get_object()
        holdings = account.holdings.all()
        total_market = sum(h.market_value for h in holdings)
        total_cost = sum(h.cost_value for h in holdings)
        total_pl = total_market - total_cost
        total_dividend = sum(h.accumulated_dividend for h in holdings)

        total_assets = account.balance + total_market
        return Response({
            'account': InvestmentAccountSerializer(account).data,
            'holdings_count': holdings.count(),
            'total_market_value': total_market,
            'total_cost': total_cost,
            'total_profit_loss': total_pl,
            'total_dividend_income': total_dividend,
            'total_market_value_cny': to_cny(total_market, account.currency),
            'initial_investment': account.initial_investment,
            'account_total_return': total_assets - account.initial_investment,
            'total_holdings_cost': total_cost,
        })


# ─── InvestmentHolding ─────────────────────────────────────────

class InvestmentHoldingViewSet(viewsets.ModelViewSet):
    filterset_fields = ['investment_account', 'symbol', 'group_tag']
    search_fields = ['symbol', 'name']
    ordering_fields = ['symbol', 'updated_at']

    def get_queryset(self):
        return InvestmentHolding.objects.filter(
            investment_account__user=self.request.user
        ).select_related('investment_account', 'investment_account__asset_type')

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return InvestmentHoldingUpdateSerializer
        return InvestmentHoldingSerializer

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        holdings = list(self.get_queryset())
        if not holdings:
            data = {
                'total_market_value': Decimal('0'),
                'total_cost': Decimal('0'),
                'total_profit_loss': Decimal('0'),
                'total_profit_loss_pct': Decimal('0'),
                'holdings_count': 0,
                'total_daily_pl': Decimal('0'),
                'total_daily_pl_pct': Decimal('0'),
                'total_dividend_income': Decimal('0'),
                'total_annualized_return': Decimal('0'),
                'by_asset_type': [],
                'by_currency': [],
            }
            return Response(InvestmentDashboardSerializer(data).data)

        # 汇总（CNY）
        total_market = Decimal('0')
        total_cost = Decimal('0')
        total_daily_pl = Decimal('0')
        total_dividend = Decimal('0')
        weighted_annualized = Decimal('0')

        by_type = {}
        by_currency = {}

        for h in holdings:
            mv_cny = to_cny(h.market_value, h.effective_currency)
            cv_cny = to_cny(h.cost_value, h.effective_currency)
            dpl_cny = to_cny(h.daily_profit_loss, h.effective_currency)
            div_cny = to_cny(h.accumulated_dividend, h.effective_currency)

            total_market += mv_cny
            total_cost += cv_cny
            total_daily_pl += dpl_cny
            total_dividend += div_cny

            # 按资产类型分组
            at = h.investment_account.asset_type
            type_key = at.code if at else 'other'
            if type_key not in by_type:
                by_type[type_key] = {
                    'asset_type_id': at.id if at else None,
                    'asset_type_name': at.name if at else '其他',
                    'asset_type_color': at.color if at else '#999',
                    'market_value': Decimal('0'),
                    'cost_value': Decimal('0'),
                    'profit_loss': Decimal('0'),
                }
            by_type[type_key]['market_value'] += mv_cny
            by_type[type_key]['cost_value'] += cv_cny
            by_type[type_key]['profit_loss'] += mv_cny - cv_cny

            # 按币种分组
            cur = h.effective_currency
            if cur not in by_currency:
                from .services import get_rate
                by_currency[cur] = {
                    'currency': cur,
                    'market_value': Decimal('0'),
                    'market_value_cny': Decimal('0'),
                    'exchange_rate': get_rate(cur),
                }
            by_currency[cur]['market_value'] += h.market_value
            by_currency[cur]['market_value_cny'] += mv_cny

        total_pl = total_market - total_cost
        total_pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else Decimal('0')
        total_daily_pl_pct = (total_daily_pl / (total_market - total_daily_pl) * 100) if (total_market - total_daily_pl) > 0 else Decimal('0')

        # 加权平均年化
        for h in holdings:
            mv_cny = to_cny(h.market_value, h.effective_currency)
            if total_market > 0 and h.annualized_return:
                weighted_annualized += h.annualized_return * (mv_cny / total_market)

        # 计算每组占比
        for key in by_type:
            by_type[key]['profit_loss_pct'] = (
                by_type[key]['profit_loss'] / by_type[key]['cost_value'] * 100
                if by_type[key]['cost_value'] > 0 else Decimal('0')
            )
            by_type[key]['weight_pct'] = (
                by_type[key]['market_value'] / total_market * 100
                if total_market > 0 else Decimal('0')
            )

        data = {
            'total_market_value': total_market,
            'total_cost': total_cost,
            'total_profit_loss': total_pl,
            'total_profit_loss_pct': total_pl_pct.quantize(Decimal('0.01')),
            'holdings_count': len(holdings),
            'total_daily_pl': total_daily_pl,
            'total_daily_pl_pct': total_daily_pl_pct.quantize(Decimal('0.01')),
            'total_dividend_income': total_dividend,
            'total_annualized_return': weighted_annualized.quantize(Decimal('0.01')),
            'by_asset_type': list(by_type.values()),
            'by_currency': list(by_currency.values()),
        }
        return Response(InvestmentDashboardSerializer(data).data)

    @action(detail=False, methods=['post'], url_path='auto-update-prices')
    def auto_update_prices(self, request):
        """自动获取所有 A 股持仓的最新价格并更新，保存每日快照，并回补近期缺失"""
        from datetime import date as date_type, timedelta
        from django.utils import timezone as tz_utils
        from .stock_data import _symbol_to_tencent
        from .management.commands.update_stock_prices import is_trading_day

        today = date_type.today()
        now_shanghai = tz_utils.localtime(tz_utils.now())

        # 仅在交易日收盘后（15:05 CST）才创建今日快照
        can_create_today_snapshot = (
            is_trading_day(today)
            and (now_shanghai.hour > 15 or (now_shanghai.hour == 15 and now_shanghai.minute >= 5))
        )

        holdings = self.get_queryset().filter(
            quantity__gt=0,
            investment_account__asset_type__category='security',
        )
        stock_holdings = [h for h in holdings if h.symbol.isdigit() and len(h.symbol) == 6]

        if not stock_holdings:
            return Response({'detail': '没有需要更新的持仓', 'updated': 0, 'total': 0,
                             'failed_symbols': [], 'backfilled': 0})

        symbols = list(set(h.symbol for h in stock_holdings))
        holding_map = {h.symbol: h for h in stock_holdings}

        # ── 1. 更新今日价格 ──────────────────────────────────────
        from .stock_data import fetch_batch_prices
        price_map = fetch_batch_prices(symbols)

        updated_count = 0
        failed_symbols = []
        for holding in stock_holdings:
            price_info = price_map.get(holding.symbol)
            if price_info and price_info.get('current_price'):
                new_price = Decimal(str(price_info['current_price']))
                new_prev = Decimal(str(price_info.get('previous_close') or holding.current_price))

                # 始终更新持仓价格（供 UI 展示）
                holding.previous_close_price = new_prev
                holding.current_price = new_price
                holding.save(update_fields=['previous_close_price', 'current_price', 'updated_at'])

                # 仅交易日收盘后创建今日快照
                if can_create_today_snapshot:
                    daily_pl = (new_price - new_prev) * holding.quantity
                    daily_pl_pct = ((new_price - new_prev) / new_prev * 100) if new_prev > 0 else Decimal('0')
                    market_value = new_price * holding.quantity
                    cost_value = holding.avg_cost * holding.quantity
                    total_pl = market_value - cost_value
                    total_pl_pct = (total_pl / cost_value * 100) if cost_value > 0 else Decimal('0')

                    DailyHoldingSnapshot.objects.update_or_create(
                        holding=holding, date=today,
                        defaults={
                            'user': request.user,
                            'symbol': holding.symbol,
                            'name': holding.name,
                            'quantity': holding.quantity,
                            'avg_cost': holding.avg_cost,
                            'close_price': new_price,
                            'previous_close': new_prev,
                            'market_value': market_value.quantize(Decimal('0.01')),
                            'cost_value': cost_value.quantize(Decimal('0.01')),
                            'daily_pl': daily_pl.quantize(Decimal('0.01')),
                            'total_pl': total_pl.quantize(Decimal('0.01')),
                            'daily_pl_pct': daily_pl_pct.quantize(Decimal('0.01')),
                            'total_pl_pct': total_pl_pct.quantize(Decimal('0.01')),
                        },
                    )

                updated_count += 1
            else:
                failed_symbols.append(holding.symbol)

        # ── 2. 回补近期缺失交易日 ────────────────────────────────
        backfilled = 0
        earliest_buy = min((h.first_buy_date for h in stock_holdings if h.first_buy_date), default=today)
        lookback_start = max(earliest_buy, today - timedelta(days=10))

        # 查询已有快照日期
        existing_dates = set(DailyHoldingSnapshot.objects.filter(
            user=request.user, date__gte=lookback_start, date__lte=today,
        ).values_list('date', flat=True))

        # 需要回补的日期：跳过周末
        missing_dates = []
        d = lookback_start
        while d < today:
            if d.weekday() < 5 and d not in existing_dates:
                missing_dates.append(d)
            d += timedelta(days=1)

        if missing_dates:
            # 通过新浪财经获取历史 K 线数据回补
            import json
            import requests as std_requests
            sina_url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'

            kline_cache = {}
            for symbol in symbols:
                tc = _symbol_to_tencent(symbol)
                if not tc:
                    continue
                try:
                    resp = std_requests.get(sina_url, params={
                        'symbol': tc, 'scale': '240', 'ma': 'no', 'datalen': '15',
                    }, timeout=10)
                    if resp.status_code == 200:
                        for item in json.loads(resp.text):
                            kline_cache.setdefault(symbol, {})[item['day']] = {
                                'close': Decimal(item['close']),
                                'pct_change': None,
                            }
                except Exception:
                    pass

            for md in missing_dates:
                md_str = md.isoformat()
                for symbol in symbols:
                    if symbol not in kline_cache or md_str not in kline_cache[symbol]:
                        continue
                    holding = holding_map.get(symbol)
                    if not holding:
                        continue

                    kline = kline_cache[symbol][md_str]
                    # 前一交易日收盘价
                    prev_close = None
                    all_kd = sorted(kline_cache[symbol].keys())
                    idx = all_kd.index(md_str)
                    if idx > 0:
                        prev_close = kline_cache[symbol][all_kd[idx - 1]]['close']

                    close_price = kline['close']
                    if prev_close is None:
                        prev_close = close_price

                    market_value = close_price * holding.quantity
                    cost_value = holding.avg_cost * holding.quantity
                    total_pl = market_value - cost_value
                    total_pl_pct = (total_pl / cost_value * 100) if cost_value > 0 else Decimal('0')
                    daily_pl = (close_price - prev_close) * holding.quantity
                    daily_pl_pct = ((close_price - prev_close) / prev_close * 100) if prev_close > 0 else Decimal('0')

                    DailyHoldingSnapshot.objects.update_or_create(
                        holding=holding, date=md,
                        defaults={
                            'user': request.user,
                            'symbol': symbol,
                            'name': holding.name,
                            'quantity': holding.quantity,
                            'avg_cost': holding.avg_cost,
                            'close_price': close_price,
                            'previous_close': prev_close,
                            'market_value': market_value.quantize(Decimal('0.01')),
                            'cost_value': cost_value.quantize(Decimal('0.01')),
                            'daily_pl': daily_pl.quantize(Decimal('0.01')),
                            'total_pl': total_pl.quantize(Decimal('0.01')),
                            'daily_pl_pct': daily_pl_pct.quantize(Decimal('0.01'))
                            if isinstance(daily_pl_pct, Decimal) else Decimal(str(daily_pl_pct)).quantize(Decimal('0.01')),
                            'total_pl_pct': total_pl_pct.quantize(Decimal('0.01')),
                        },
                    )
                    backfilled += 1

        detail = f'成功更新 {updated_count} 个持仓价格'
        if backfilled:
            detail += f'，回补 {backfilled} 条历史快照'
        if not can_create_today_snapshot and updated_count > 0:
            detail += '（今日快照将在收盘后自动生成）'

        return Response({
            'detail': detail,
            'updated': updated_count,
            'total': len(stock_holdings),
            'failed_symbols': list(set(failed_symbols)),
            'backfilled': backfilled,
        })

    @action(detail=False, methods=['post'])
    @db_transaction.atomic
    def batch_update_prices(self, request):
        updates = request.data.get('updates', [])
        if not isinstance(updates, list) or len(updates) > 100:
            return Response({'detail': 'updates 列表无效或超过 100 条限制'}, status=status.HTTP_400_BAD_REQUEST)
        for item in updates:
            holding_id = item.get('holding_id')
            new_price = item.get('current_price')
            if not holding_id or new_price is None:
                continue
            try:
                new_price = Decimal(str(new_price))
                if new_price < 0:
                    continue
            except Exception:
                continue
            try:
                holding = InvestmentHolding.objects.select_for_update().get(
                    id=holding_id,
                    investment_account__user=request.user,
                )
                holding.previous_close_price = holding.current_price
                holding.current_price = new_price
                holding.save(update_fields=['previous_close_price', 'current_price', 'updated_at'])
            except InvestmentHolding.DoesNotExist:
                continue
        return Response({'detail': '价格更新成功'})

    @action(detail=False, methods=['get'], url_path='daily-snapshots')
    def daily_snapshots(self, request):
        """查询每日持仓快照"""
        queryset = DailyHoldingSnapshot.objects.filter(
            user=request.user
        ).order_by('-date', 'symbol')

        symbol = request.query_params.get('symbol')
        if symbol:
            queryset = queryset.filter(symbol=symbol)

        date_param = request.query_params.get('date')
        if date_param:
            queryset = queryset.filter(date=date_param)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)

        # 汇总当日盈亏
        snapshots = list(queryset[:500])
        daily_summary = {}
        for s in snapshots:
            if s.date not in daily_summary:
                daily_summary[s.date] = {'daily_pl': Decimal('0'), 'total_pl': Decimal('0'), 'count': 0}
            daily_summary[s.date]['daily_pl'] += s.daily_pl
            daily_summary[s.date]['total_pl'] += s.total_pl
            daily_summary[s.date]['count'] += 1

        return Response({
            'snapshots': DailyHoldingSnapshotSerializer(snapshots, many=True).data,
            'daily_summary': [
                {'date': d, **{k: str(v) for k, v in v.items()}}
                for d, v in sorted(daily_summary.items(), reverse=True)
            ],
        })


# ─── InvestmentTransaction ─────────────────────────────────────

class InvestmentTransactionViewSet(viewsets.ModelViewSet):
    filterset_fields = ['investment_account', 'transaction_type', 'symbol', 'date']
    search_fields = ['symbol', 'name', 'note']
    ordering_fields = ['date', 'amount', 'created_at']

    def get_queryset(self):
        return InvestmentTransaction.objects.filter(
            investment_account__user=self.request.user
        ).select_related('investment_account', 'investment_account__asset_type', 'holding')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return InvestmentTransactionCreateSerializer
        return InvestmentTransactionSerializer

    def create(self, request, *args, **kwargs):
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            transaction = serializer.save()

            from .fee_calculator import calculate_buy_fees, calculate_sell_fees

            if transaction.transaction_type == 'buy':
                amount = transaction.quantity * transaction.price
                fees = calculate_buy_fees(transaction.price, transaction.quantity)
                if transaction.fee == 0:
                    transaction.fee = fees['total_fees']
                transaction.amount = amount
                transaction.save(update_fields=['amount', 'fee'])

            elif transaction.transaction_type == 'sell':
                amount = transaction.quantity * transaction.price
                fees = calculate_sell_fees(transaction.price, transaction.quantity)
                if transaction.fee == 0:
                    transaction.fee = fees['total_fees']
                transaction.amount = amount
                if transaction.profit_loss == 0 and transaction.holding:
                    holding = transaction.holding
                    transaction.profit_loss = (transaction.price - holding.avg_cost) * transaction.quantity - transaction.fee
                transaction.save(update_fields=['amount', 'fee', 'profit_loss'])

            update_holding_from_transaction(transaction)

        output_serializer = InvestmentTransactionSerializer(transaction)
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


# ─── DividendRecord ─────────────────────────────────────────────

class DividendRecordViewSet(viewsets.ModelViewSet):
    filterset_fields = ['investment_account', 'dividend_type', 'symbol']
    search_fields = ['symbol', 'name', 'note']
    ordering_fields = ['ex_date', 'created_at']

    def get_queryset(self):
        return DividendRecord.objects.filter(
            investment_account__user=self.request.user
        ).select_related('investment_account', 'holding', 'transaction')

    def get_serializer_class(self):
        if self.action == 'create':
            return DividendRecordCreateSerializer
        return DividendRecordSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with db_transaction.atomic():
            record = serializer.save()
            handle_dividend(record)
        output_serializer = DividendRecordSerializer(record)
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
