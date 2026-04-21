from datetime import date
from decimal import Decimal

from .models import ExchangeRate


def to_cny(amount, currency, target_date=None):
    """将任意币种金额转换为人民币"""
    if currency == 'CNY' or not currency:
        return amount
    if target_date is None:
        target_date = date.today()

    rate_obj = ExchangeRate.objects.filter(
        target_currency=currency,
        rate_date__lte=target_date,
    ).order_by('-rate_date').first()

    if rate_obj is None:
        return amount

    return amount * rate_obj.rate


def get_rate(currency, target_date=None):
    """获取汇率（目标币种 -> CNY）"""
    if currency == 'CNY' or not currency:
        return Decimal('1')
    if target_date is None:
        target_date = date.today()

    rate_obj = ExchangeRate.objects.filter(
        target_currency=currency,
        rate_date__lte=target_date,
    ).order_by('-rate_date').first()

    return rate_obj.rate if rate_obj else Decimal('1')


def update_holding_from_transaction(transaction):
    """根据交易记录自动更新持仓"""
    from .models import InvestmentHolding

    # 入金/出金/费用只影响账户余额
    if transaction.transaction_type in ('deposit', 'withdraw', 'fee'):
        _update_account_balance(transaction)
        return

    holding, created = InvestmentHolding.objects.get_or_create(
        investment_account=transaction.investment_account,
        symbol=transaction.symbol,
        defaults={
            'name': transaction.name,
            'current_price': transaction.price,
            'first_buy_date': transaction.date if transaction.transaction_type == 'buy' else None,
            'currency': '',
        },
    )

    if not created:
        holding.name = transaction.name

    if transaction.transaction_type == 'buy':
        total_cost = (holding.avg_cost * holding.quantity
                      + transaction.price * transaction.quantity
                      + transaction.fee)
        total_qty = holding.quantity + transaction.quantity
        holding.avg_cost = total_cost / total_qty if total_qty > 0 else Decimal('0')
        holding.quantity = total_qty
        holding.current_price = transaction.price
        if not holding.first_buy_date:
            holding.first_buy_date = transaction.date

    elif transaction.transaction_type == 'sell':
        holding.quantity -= transaction.quantity
        holding.current_price = transaction.price
        if holding.quantity <= 0:
            holding.quantity = Decimal('0')
            holding.avg_cost = Decimal('0')

    elif transaction.transaction_type in ('dividend', 'interest'):
        if holding.quantity > 0:
            holding.accumulated_dividend += transaction.amount
            new_cost = holding.avg_cost * holding.quantity - transaction.amount
            if new_cost > 0 and holding.quantity > 0:
                holding.avg_cost = new_cost / holding.quantity
            else:
                holding.avg_cost = Decimal('0')

    elif transaction.transaction_type == 'dividend_reinvest':
        holding.accumulated_dividend += transaction.amount
        total_cost = holding.avg_cost * holding.quantity + transaction.price * transaction.quantity
        total_qty = holding.quantity + transaction.quantity
        holding.avg_cost = total_cost / total_qty if total_qty > 0 else Decimal('0')
        holding.quantity = total_qty
        holding.current_price = transaction.price

    elif transaction.transaction_type == 'split':
        if transaction.quantity > 0:
            holding.quantity = holding.quantity * transaction.quantity
            holding.avg_cost = holding.avg_cost / transaction.quantity

    holding.save()


def _update_account_balance(transaction):
    """根据入金/出金/费用更新账户余额"""
    account = transaction.investment_account
    if transaction.transaction_type == 'deposit':
        account.balance += transaction.amount
    elif transaction.transaction_type == 'withdraw':
        account.balance -= transaction.amount
    elif transaction.transaction_type == 'fee':
        account.balance -= transaction.amount
    account.save(update_fields=['balance'])


def handle_dividend(dividend_record):
    """处理分红记录：创建关联交易，更新持仓"""
    from .models import InvestmentTransaction

    if dividend_record.dividend_type == 'cash':
        txn = InvestmentTransaction.objects.create(
            investment_account=dividend_record.investment_account,
            holding=dividend_record.holding,
            symbol=dividend_record.symbol,
            name=dividend_record.name,
            transaction_type='dividend',
            quantity=dividend_record.quantity,
            price=dividend_record.dividend_per_unit,
            amount=dividend_record.net_amount,
            dividend_per_unit=dividend_record.dividend_per_unit,
            date=dividend_record.ex_date,
            note=dividend_record.note or f'{dividend_record.name} 现金分红',
        )
        dividend_record.transaction = txn
        dividend_record.save(update_fields=['transaction'])

        # 分红到账：增加账户余额
        account = dividend_record.investment_account
        account.balance += dividend_record.net_amount
        account.save(update_fields=['balance'])

        # 更新持仓成本和累计分红
        update_holding_from_transaction(txn)

    elif dividend_record.dividend_type == 'reinvest':
        # 1. 分红交易
        txn_div = InvestmentTransaction.objects.create(
            investment_account=dividend_record.investment_account,
            holding=dividend_record.holding,
            symbol=dividend_record.symbol,
            name=dividend_record.name,
            transaction_type='dividend',
            quantity=dividend_record.quantity,
            price=dividend_record.dividend_per_unit,
            amount=dividend_record.net_amount,
            dividend_per_unit=dividend_record.dividend_per_unit,
            date=dividend_record.ex_date,
            note=f'{dividend_record.name} 分红（再投资）',
        )

        # 2. 再投资买入交易
        reinvest_price = dividend_record.holding.current_price if dividend_record.holding else dividend_record.dividend_per_unit
        reinvest_qty = dividend_record.net_amount / reinvest_price if reinvest_price > 0 else Decimal('0')
        txn_buy = InvestmentTransaction.objects.create(
            investment_account=dividend_record.investment_account,
            holding=dividend_record.holding,
            symbol=dividend_record.symbol,
            name=dividend_record.name,
            transaction_type='dividend_reinvest',
            quantity=reinvest_qty,
            price=reinvest_price,
            amount=dividend_record.net_amount,
            related_transaction=txn_div,
            date=dividend_record.ex_date,
            note=f'{dividend_record.name} 分红再投资',
        )

        dividend_record.transaction = txn_div
        dividend_record.save(update_fields=['transaction'])

        # 更新持仓（分红再投资模式）
        update_holding_from_transaction(txn_buy)

    elif dividend_record.dividend_type == 'interest':
        txn = InvestmentTransaction.objects.create(
            investment_account=dividend_record.investment_account,
            holding=dividend_record.holding,
            symbol=dividend_record.symbol,
            name=dividend_record.name,
            transaction_type='interest',
            quantity=dividend_record.quantity,
            price=dividend_record.dividend_per_unit,
            amount=dividend_record.net_amount,
            dividend_per_unit=dividend_record.dividend_per_unit,
            date=dividend_record.ex_date,
            note=dividend_record.note or f'{dividend_record.name} 利息收入',
        )
        dividend_record.transaction = txn
        dividend_record.save(update_fields=['transaction'])

        account = dividend_record.investment_account
        account.balance += dividend_record.net_amount
        account.save(update_fields=['balance'])

        update_holding_from_transaction(txn)
