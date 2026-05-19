from decimal import Decimal

from rest_framework import serializers
from .models import (
    AssetType, ExchangeRate,
    InvestmentAccount, InvestmentHolding, InvestmentTransaction,
    DividendRecord, DailyHoldingSnapshot,
)
from ..transactions.models import Account
from .services import to_cny, get_rate


# ─── AssetType ────────────────────────────────────────────────

class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetType
        fields = ['id', 'user', 'code', 'name', 'category', 'icon', 'color', 'is_active', 'sort_order']
        read_only_fields = ['id']

    def validate(self, data):
        if data.get('sort_order') is None:
            data['sort_order'] = 0
        return data


# ─── ExchangeRate ──────────────────────────────────────────────

class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = ['id', 'base_currency', 'target_currency', 'rate', 'rate_date', 'source', 'created_at']
        read_only_fields = ['id', 'created_at']


# ─── InvestmentAccount ─────────────────────────────────────────

class AssetTypeBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetType
        fields = ['id', 'code', 'name', 'category', 'icon', 'color']


class FundAccountBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'name', 'account_type', 'balance']


class InvestmentAccountSerializer(serializers.ModelSerializer):
    asset_type_detail = AssetTypeBriefSerializer(source='asset_type', read_only=True)
    fund_account_detail = FundAccountBriefSerializer(source='fund_account', read_only=True)
    total_market_value = serializers.SerializerMethodField()
    total_market_value_cny = serializers.SerializerMethodField()
    total_assets = serializers.SerializerMethodField()
    total_holdings_cost = serializers.SerializerMethodField()
    account_total_return = serializers.SerializerMethodField()
    account_total_return_pct = serializers.SerializerMethodField()

    class Meta:
        model = InvestmentAccount
        fields = [
            'id', 'name', 'broker', 'asset_type', 'asset_type_detail',
            'fund_account', 'fund_account_detail',
            'currency', 'balance', 'initial_investment',
            'total_market_value', 'total_market_value_cny', 'total_assets',
            'total_holdings_cost', 'account_total_return', 'account_total_return_pct',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_fields(self):
        fields = super().get_fields()
        if self.instance and getattr(self.instance, 'pk', None):
            fields['balance'].read_only = True
        return fields

    def _calc_holding_totals(self, obj):
        """一次遍历计算所有持仓汇总值"""
        cache = self.context.get('_holding_totals_cache', {})
        if obj.id not in cache:
            market_value = Decimal('0')
            holdings_cost = Decimal('0')
            for h in obj.holdings.all():
                market_value += h.market_value
                holdings_cost += h.cost_value
            cache[obj.id] = {
                'market_value': market_value,
                'holdings_cost': holdings_cost,
            }
            self.context['_holding_totals_cache'] = cache
        return cache[obj.id]

    def get_total_market_value(self, obj):
        return self._calc_holding_totals(obj)['market_value']

    def get_total_market_value_cny(self, obj):
        return to_cny(self.get_total_market_value(obj), obj.currency)

    def get_total_assets(self, obj):
        return obj.balance + self.get_total_market_value(obj)

    def get_total_holdings_cost(self, obj):
        return self._calc_holding_totals(obj)['holdings_cost']

    def get_account_total_return(self, obj):
        return self.get_total_assets(obj) - obj.initial_investment

    def get_account_total_return_pct(self, obj):
        if obj.initial_investment == 0:
            return Decimal('0')
        return (self.get_account_total_return(obj) / obj.initial_investment) * 100


# ─── InvestmentHolding ─────────────────────────────────────────

class InvestmentHoldingSerializer(serializers.ModelSerializer):
    market_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    cost_value = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    profit_loss = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    profit_loss_pct = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    holding_days = serializers.IntegerField(read_only=True)
    daily_profit_loss = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    daily_profit_loss_pct = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    total_return_rate = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    annualized_return = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)
    daily_avg_cost = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    effective_currency = serializers.CharField(read_only=True)
    market_value_cny = serializers.SerializerMethodField()
    cost_value_cny = serializers.SerializerMethodField()
    account_name = serializers.CharField(source='investment_account.name', read_only=True)
    account_type_name = serializers.SerializerMethodField()
    asset_type_color = serializers.SerializerMethodField()

    class Meta:
        model = InvestmentHolding
        fields = [
            'id', 'investment_account', 'account_name', 'account_type_name', 'asset_type_color',
            'symbol', 'name', 'quantity', 'avg_cost', 'current_price',
            'previous_close_price', 'accumulated_dividend', 'group_tag',
            'currency', 'effective_currency',
            'market_value', 'cost_value', 'profit_loss', 'profit_loss_pct',
            'market_value_cny', 'cost_value_cny',
            'holding_days', 'daily_profit_loss', 'daily_profit_loss_pct',
            'total_return_rate', 'annualized_return', 'daily_avg_cost',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at']

    def get_market_value_cny(self, obj):
        return to_cny(obj.market_value, obj.effective_currency)

    def get_cost_value_cny(self, obj):
        return to_cny(obj.cost_value, obj.effective_currency)

    def get_account_type_name(self, obj):
        at = obj.investment_account.asset_type
        return at.name if at else ''

    def get_asset_type_color(self, obj):
        at = obj.investment_account.asset_type
        return at.color if at else '#1677ff'


class InvestmentHoldingUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentHolding
        fields = ['current_price', 'previous_close_price', 'group_tag']


# ─── InvestmentTransaction ─────────────────────────────────────

class InvestmentTransactionSerializer(serializers.ModelSerializer):
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)
    account_name = serializers.CharField(source='investment_account.name', read_only=True)

    class Meta:
        model = InvestmentTransaction
        fields = [
            'id', 'investment_account', 'account_name', 'holding',
            'symbol', 'name',
            'transaction_type', 'transaction_type_display',
            'quantity', 'price', 'amount', 'fee', 'profit_loss',
            'dividend_per_unit', 'related_transaction',
            'date', 'note', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class InvestmentTransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentTransaction
        fields = [
            'investment_account', 'holding', 'symbol', 'name',
            'transaction_type', 'quantity', 'price', 'amount',
            'fee', 'profit_loss', 'dividend_per_unit', 'related_transaction',
            'date', 'note',
        ]

    def validate_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError('数量不能为负')
        return value

    def validate_price(self, value):
        if value < 0:
            raise serializers.ValidationError('价格不能为负')
        return value

    def validate(self, data):
        request = self.context.get('request')
        account = data.get('investment_account')
        holding = data.get('holding')
        transaction_type = data.get('transaction_type')

        if account and request and account.user != request.user:
            raise serializers.ValidationError({'investment_account': '无权操作此投资账户'})
        if holding and account and holding.investment_account_id != account.id:
            raise serializers.ValidationError({'holding': '持仓不属于所选账户'})
        if transaction_type in ('buy', 'sell') and (not data.get('quantity') or data.get('quantity') <= 0):
            raise serializers.ValidationError({'quantity': f'{transaction_type}操作数量必须大于0'})
        if transaction_type in ('buy', 'sell') and (not data.get('price') or data.get('price') <= 0):
            raise serializers.ValidationError({'price': f'{transaction_type}操作价格必须大于0'})
        return data


# ─── Dashboard ──────────────────────────────────────────────────

class InvestmentDashboardSerializer(serializers.Serializer):
    total_market_value = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_cost = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_profit_loss = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_profit_loss_pct = serializers.DecimalField(max_digits=8, decimal_places=2)
    holdings_count = serializers.IntegerField()
    total_daily_pl = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_daily_pl_pct = serializers.DecimalField(max_digits=8, decimal_places=2)
    total_dividend_income = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_annualized_return = serializers.DecimalField(max_digits=8, decimal_places=2)
    by_asset_type = serializers.ListField()
    by_currency = serializers.ListField()


# ─── DividendRecord ─────────────────────────────────────────────

class DividendRecordSerializer(serializers.ModelSerializer):
    dividend_type_display = serializers.CharField(source='get_dividend_type_display', read_only=True)
    account_name = serializers.CharField(source='investment_account.name', read_only=True)

    class Meta:
        model = DividendRecord
        fields = [
            'id', 'investment_account', 'account_name', 'holding',
            'symbol', 'name', 'dividend_type', 'dividend_type_display',
            'ex_date', 'pay_date', 'dividend_per_unit', 'quantity',
            'total_amount', 'tax', 'net_amount',
            'transaction', 'note', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'transaction']


class DividendRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DividendRecord
        fields = [
            'investment_account', 'holding', 'symbol', 'name',
            'dividend_type', 'ex_date', 'pay_date',
            'dividend_per_unit', 'quantity',
            'total_amount', 'tax', 'net_amount', 'note',
        ]

    def validate_dividend_per_unit(self, value):
        if value <= 0:
            raise serializers.ValidationError('每单位分红必须大于0')
        return value

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('数量必须大于0')
        return value

    def validate(self, data):
        from decimal import Decimal
        account = data.get('investment_account')
        holding = data.get('holding')
        if holding and account and holding.investment_account_id != account.id:
            raise serializers.ValidationError({'holding': '持仓不属于所选账户'})

        expected = data['dividend_per_unit'] * data['quantity']
        total = data.get('total_amount', Decimal('0'))
        if abs(total - expected) > Decimal('0.01'):
            raise serializers.ValidationError({'total_amount': f'总金额应为每单位分红 × 数量 = {expected:.4f}'})
        return data


# ─── DailyHoldingSnapshot ──────────────────────────────────────────

class DailyHoldingSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyHoldingSnapshot
        fields = [
            'id', 'holding', 'symbol', 'name', 'date',
            'quantity', 'avg_cost', 'close_price', 'previous_close',
            'market_value', 'cost_value',
            'daily_pl', 'total_pl', 'daily_pl_pct', 'total_pl_pct',
            'created_at',
        ]
