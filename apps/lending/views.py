from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Q

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
        return LendingRecord.objects.filter(
            user=self.request.user
        ).prefetch_related('repayments')

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return LendingRecordCreateSerializer
        return LendingRecordSerializer

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

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
        repayment = serializer.save()
        record = repayment.lending_record

        agg = record.repayments.aggregate(
            total_repaid=Sum('amount', default=0),
            total_interest=Sum('interest', default=0),
        )
        record.repaid_amount = agg['total_repaid']
        record.interest_amount = agg['total_interest']

        if record.repaid_amount >= record.amount:
            record.status = 'settled'
        elif record.repaid_amount > 0:
            record.status = 'partial'
        else:
            record.status = 'outstanding'
        record.save(update_fields=['repaid_amount', 'interest_amount', 'status', 'updated_at'])
