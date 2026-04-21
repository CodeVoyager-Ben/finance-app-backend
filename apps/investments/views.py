from decimal import Decimal

from django.db import models as db_models
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import (
    AssetType, ExchangeRate,
    InvestmentAccount, InvestmentHolding, InvestmentTransaction,
    DividendRecord,
)
from .serializers import (
    AssetTypeSerializer,
    ExchangeRateSerializer,
    InvestmentAccountSerializer,
    InvestmentHoldingSerializer, InvestmentHoldingUpdateSerializer,
    InvestmentTransactionSerializer, InvestmentTransactionCreateSerializer,
    InvestmentDashboardSerializer,
    DividendRecordSerializer, DividendRecordCreateSerializer,
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
            return Response({'detail': '系统预设类型不可修改'}, status=status.HTTP_403_FORBIDDEN)
        serializer.save()

    def perform_destroy(self, instance):
        if instance.user is None:
            return Response({'detail': '系统预设类型不可删除'}, status=status.HTTP_403_FORBIDDEN)
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

        return Response({
            'account': InvestmentAccountSerializer(account).data,
            'holdings_count': holdings.count(),
            'total_market_value': total_market,
            'total_cost': total_cost,
            'total_profit_loss': total_pl,
            'total_dividend_income': total_dividend,
            'total_market_value_cny': to_cny(total_market, account.currency),
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

    @action(detail=False, methods=['post'])
    def batch_update_prices(self, request):
        updates = request.data.get('updates', [])
        for item in updates:
            holding_id = item.get('holding_id')
            new_price = item.get('current_price')
            if holding_id and new_price is not None:
                try:
                    holding = InvestmentHolding.objects.get(
                        id=holding_id,
                        investment_account__user=request.user,
                    )
                    holding.previous_close_price = holding.current_price
                    holding.current_price = Decimal(str(new_price))
                    holding.save(update_fields=['previous_close_price', 'current_price', 'updated_at'])
                except InvestmentHolding.DoesNotExist:
                    continue
        return Response({'detail': '价格更新成功'})


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
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        transaction = serializer.save()
        if transaction.transaction_type in ('buy', 'sell'):
            transaction.amount = transaction.quantity * transaction.price
            transaction.save(update_fields=['amount'])
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
        record = serializer.save()
        handle_dividend(record)
        # 返回完整序列化器以包含 display 字段
        output_serializer = DividendRecordSerializer(record)
        headers = self.get_success_headers(output_serializer.data)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED, headers=headers)
