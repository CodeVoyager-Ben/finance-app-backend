from django.contrib import admin
from .models import (
    AssetType, ExchangeRate,
    InvestmentAccount, InvestmentHolding, InvestmentTransaction,
    DividendRecord,
)


class InvestmentHoldingInline(admin.TabularInline):
    model = InvestmentHolding
    extra = 0
    readonly_fields = ['market_value', 'cost_value', 'profit_loss']


@admin.register(InvestmentAccount)
class InvestmentAccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'asset_type', 'currency', 'balance', 'is_active', 'created_at']
    list_filter = ['asset_type', 'currency', 'is_active']
    search_fields = ['name', 'broker']
    inlines = [InvestmentHoldingInline]


@admin.register(InvestmentHolding)
class InvestmentHoldingAdmin(admin.ModelAdmin):
    list_display = ['symbol', 'name', 'investment_account', 'quantity', 'avg_cost', 'current_price', 'group_tag']
    list_filter = ['investment_account__asset_type']
    search_fields = ['symbol', 'name']


@admin.register(InvestmentTransaction)
class InvestmentTransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'investment_account', 'transaction_type', 'symbol', 'name', 'quantity', 'price', 'amount']
    list_filter = ['transaction_type', 'date']
    search_fields = ['symbol', 'name', 'note']


@admin.register(AssetType)
class AssetTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'icon', 'color', 'is_active', 'sort_order']
    list_filter = ['category', 'is_active']


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['target_currency', 'base_currency', 'rate', 'rate_date', 'source']
    list_filter = ['target_currency']


@admin.register(DividendRecord)
class DividendRecordAdmin(admin.ModelAdmin):
    list_display = ['ex_date', 'symbol', 'name', 'dividend_type', 'total_amount', 'tax', 'net_amount']
    list_filter = ['dividend_type', 'ex_date']
