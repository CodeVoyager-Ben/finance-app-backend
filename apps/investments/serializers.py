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

    class Meta:
        model = InvestmentAccount
        fields = [
            'id', 'name', 'broker', 'asset_type', 'asset_type_detail',
            'fund_account', 'fund_account_detail',
            'currency', 'balance', 'total_market_value', 'total_market_value_cny', 'total_assets',
            'is_active', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def get_total_market_value(self, obj):
        return sum(h.market_value for h in obj.holdings.all())

    def get_total_market_value_cny(self, obj):
        total = self.get_total_market_value(obj)
        return to_cny(total, obj.currency)

    def get_total_assets(self, obj):
        return obj.balance + self.get_total_market_value(obj)


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
