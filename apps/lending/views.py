from decimal import Decimal

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.db.models import F, Sum, Q
from apps.transactions.models import Account

from .models import LendingRecord, Repayment
from .serializers import (
    LendingRecordSerializer, LendingRecordCreateSerializer,
    RepaymentSerializer, RepaymentCreateSerializer,
    LendingSummarySerializer,
)


class LendingRecordViewSet(viewsets.ModelViewSet):
    """借贷记录管理"""
    filterset_fields = ['record_type', 'counterparty', 'status', 'date']
    search_fields = ['counterparty', 'reason', 'note']
    ordering_fields = ['date', 'amount', 'created_at']

    def get_queryset(self):
        qs = LendingRecord.objects.filter(
            user=self.request.user
        ).prefetch_related('repayments')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return LendingRecordCreateSerializer
        return LendingRecordSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.repayments.exists():
            if 'amount' in serializer.validated_data and serializer.validated_data['amount'] != instance.amount:
                raise ValidationError('已有还款记录的借贷金额不可修改')
            if 'record_type' in serializer.validated_data:
                raise ValidationError('已有还款记录的借贷类型不可修改')
        serializer.save()

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """借贷汇总统计"""
        qs = self.get_queryset()
        active = qs.exclude(status__in=['settled', 'written_off'])

        lend_qs = active.filter(record_type='lend')
        borrow_qs = active.filter(record_type='borrow')

        total_lent = lend_qs.aggregate(s=Sum('amount', default=0))['s']
        total_borrowed = borrow_qs.aggregate(s=Sum('amount', default=0))['s']
        total_lent_remaining = lend_qs.aggregate(
            s=Sum('amount', default=0) - Sum('repaid_amount', default=0)
        )['s']
        total_borrowed_remaining = borrow_qs.aggregate(
            s=Sum('amount', default=0) - Sum('repaid_amount', default=0)
        )['s']

        all_interest = qs.aggregate(
            total_interest_earned=Sum('interest_amount', filter=Q(record_type='lend'), default=0),
            total_interest_paid=Sum('interest_amount', filter=Q(record_type='borrow'), default=0),
        )

        data = {
            'total_lent': total_lent,
            'total_borrowed': total_borrowed,
            'total_lent_remaining': total_lent_remaining,
            'total_borrowed_remaining': total_borrowed_remaining,
            'total_interest_earned': all_interest['total_interest_earned'],
            'total_interest_paid': all_interest['total_interest_paid'],
        }
        return Response(LendingSummarySerializer(data).data)


def _update_account_for_repayment(repayment, revert=False):
    """还款时更新关联账户余额"""
    if not repayment.account_id:
        return
    account = Account.objects.select_for_update().get(pk=repayment.account_id)
    amount = repayment.amount
    if revert:
        amount = -amount
    if repayment.repay_type == 'collect':
        account.balance = F('balance') + amount
    elif repayment.repay_type == 'repay':
        account.balance = F('balance') - amount
    account.save(update_fields=['balance'])


def _recalculate_record(record):
    """重新计算借贷记录的还款汇总"""
    agg = record.repayments.aggregate(
        total_repaid=Sum('amount', default=0),
        total_interest=Sum('interest', default=0),
    )
    record.repaid_amount = agg['total_repaid']
    record.interest_amount = agg['total_interest']

    principal_repaid = agg['total_repaid'] - agg['total_interest']
    if principal_repaid >= record.amount and record.amount > 0:
        record.status = 'settled'
    elif agg['total_repaid'] > 0:
        record.status = 'partial'
    else:
        record.status = 'outstanding'
    record.save(update_fields=['repaid_amount', 'interest_amount', 'status', 'updated_at'])


class RepaymentViewSet(viewsets.ModelViewSet):
    """还款记录管理"""
    filterset_fields = ['lending_record', 'repay_type', 'date']
    ordering_fields = ['date', 'amount', 'created_at']

    def get_queryset(self):
        return Repayment.objects.filter(
            lending_record__user=self.request.user
        ).select_related('lending_record', 'account')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return RepaymentCreateSerializer
        return RepaymentSerializer

    def perform_create(self, serializer):
        with db_transaction.atomic():
            record = LendingRecord.objects.select_for_update().get(
                pk=serializer.validated_data['lending_record'].pk
            )
            remaining = record.amount - record.repaid_amount
            new_amount = serializer.validated_data.get('amount', Decimal('0'))
            if new_amount > remaining:
                raise ValidationError(f'还款金额({new_amount})超过剩余金额({remaining})')

            repayment = serializer.save()
            _update_account_for_repayment(repayment)
            _recalculate_record(record)

    def perform_update(self, serializer):
        with db_transaction.atomic():
            old_repayment = serializer.instance
            _update_account_for_repayment(old_repayment, revert=True)
            old_record = old_repayment.lending_record
            record = LendingRecord.objects.select_for_update().get(pk=old_record.pk)

            remaining = record.amount - record.repaid_amount + old_repayment.amount
            new_amount = serializer.validated_data.get('amount', old_repayment.amount)
            if new_amount > remaining:
                raise ValidationError(f'还款金额({new_amount})超过剩余金额({remaining})')

            repayment = serializer.save()
            _update_account_for_repayment(repayment)
            _recalculate_record(record)

    def perform_destroy(self, instance):
        with db_transaction.atomic():
            _update_account_for_repayment(instance, revert=True)
            record = LendingRecord.objects.select_for_update().get(
                pk=instance.lending_record.pk
            )
            instance.delete()
            _recalculate_record(record)
