from rest_framework import serializers
from .models import LendingRecord, Repayment


class RepaymentSerializer(serializers.ModelSerializer):
    repay_type_display = serializers.CharField(source='get_repay_type_display', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True, default='')

    class Meta:
        model = Repayment
        fields = [
            'id', 'lending_record', 'repay_type', 'repay_type_display',
            'amount', 'interest', 'account', 'account_name',
            'date', 'note', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class RepaymentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Repayment
        fields = ['lending_record', 'repay_type', 'amount', 'interest', 'account', 'date', 'note']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('金额必须大于0')
        return value

    def validate(self, data):
        record = data['lending_record']
        if record.user != self.context['request'].user:
            raise serializers.ValidationError('无权操作此记录')
        remaining = float(record.remaining_amount)
        principal = float(data['amount']) - float(data.get('interest', 0))
        if principal > remaining:
            raise serializers.ValidationError(f'还款本金超出剩余金额 ¥{remaining:.2f}')
        return data


class LendingRecordSerializer(serializers.ModelSerializer):
    record_type_display = serializers.CharField(source='get_record_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True, default='')
    remaining_amount = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    repayments = RepaymentSerializer(many=True, read_only=True)

    class Meta:
        model = LendingRecord
        fields = [
            'id', 'record_type', 'record_type_display', 'counterparty',
            'amount', 'repaid_amount', 'interest_amount', 'remaining_amount',
            'account', 'account_name', 'status', 'status_display',
            'date', 'expected_return_date', 'reason', 'note',
            'created_at', 'updated_at', 'repayments',
        ]
        read_only_fields = ['id', 'repaid_amount', 'interest_amount', 'status', 'created_at', 'updated_at']


class LendingRecordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LendingRecord
        fields = ['record_type', 'counterparty', 'amount', 'account', 'date', 'expected_return_date', 'reason', 'note']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('金额必须大于0')
        return value


class LendingSummarySerializer(serializers.Serializer):
    """借贷汇总"""
    total_lent = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_borrowed = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_lent_remaining = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_borrowed_remaining = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_interest_earned = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_interest_paid = serializers.DecimalField(max_digits=15, decimal_places=2)
