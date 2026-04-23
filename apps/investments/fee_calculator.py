from decimal import Decimal

COMMISSION_RATE = Decimal('0.00025')    # 0.025% (万2.5)
COMMISSION_MIN = Decimal('5.00')        # 最低 5 元
STAMP_DUTY_RATE = Decimal('0.0005')     # 0.05% 卖出印花税
TRANSFER_FEE_RATE = Decimal('0.00001')  # 0.001% 过户费


def calculate_sell_fees(price, quantity):
    """计算按给定价格卖出时的预估费用"""
    amount = Decimal(str(price)) * Decimal(str(quantity))

    commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
    stamp_duty = amount * STAMP_DUTY_RATE
    transfer_fee = amount * TRANSFER_FEE_RATE
    total_fees = commission + stamp_duty + transfer_fee

    return {
        'trade_amount': amount.quantize(Decimal('0.01')),
        'commission': commission.quantize(Decimal('0.01')),
        'stamp_duty': stamp_duty.quantize(Decimal('0.01')),
        'transfer_fee': transfer_fee.quantize(Decimal('0.01')),
        'total_fees': total_fees.quantize(Decimal('0.01')),
        'net_proceeds': (amount - total_fees).quantize(Decimal('0.01')),
    }


def calculate_buy_fees(price, quantity):
    """计算按给定价格买入时的预估费用（买入不收印花税）"""
    amount = Decimal(str(price)) * Decimal(str(quantity))

    commission = max(amount * COMMISSION_RATE, COMMISSION_MIN)
    transfer_fee = amount * TRANSFER_FEE_RATE
    total_fees = commission + transfer_fee

    return {
        'trade_amount': amount.quantize(Decimal('0.01')),
        'commission': commission.quantize(Decimal('0.01')),
        'stamp_duty': Decimal('0.00'),
        'transfer_fee': transfer_fee.quantize(Decimal('0.01')),
        'total_fees': total_fees.quantize(Decimal('0.01')),
        'net_cost': (amount + total_fees).quantize(Decimal('0.01')),
    }
