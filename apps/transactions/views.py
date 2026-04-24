from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from datetime import datetime, timedelta

from .models import Account, Category, Transaction, Budget
from .serializers import (
    AccountSerializer, CategorySerializer,
    TransactionSerializer, TransactionCreateSerializer,
    DailySummarySerializer, MonthlySummarySerializer, CategorySummarySerializer,
    BudgetSerializer,
)


class AccountViewSet(viewsets.ModelViewSet):
    serializer_class = AccountSerializer

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    def get_queryset(self):
        qs = Category.objects.filter(user=self.request.user, parent__isnull=True)
        category_type = self.request.query_params.get('category_type')
        if category_type:
            qs = qs.filter(category_type=category_type)
        return qs

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TransactionViewSet(viewsets.ModelViewSet):
    filterset_fields = ['account', 'category', 'transaction_type', 'date']
    search_fields = ['note', 'category__name']
    ordering_fields = ['date', 'amount', 'created_at']

    def get_queryset(self):
        qs = Transaction.objects.filter(user=self.request.user).select_related('account', 'category')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            qs = qs.filter(date__gte=start_date)
        if end_date:
            qs = qs.filter(date__lte=end_date)
        return qs

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return TransactionCreateSerializer
        return TransactionSerializer

    def perform_create(self, serializer):
        transaction = serializer.save(user=self.request.user)
        self._update_account_balance(transaction)

    def perform_update(self, serializer):
        old = self.get_object()
        self._revert_account_balance(old)
        transaction = serializer.save()
        self._update_account_balance(transaction)

    def perform_destroy(self, instance):
        self._revert_account_balance(instance)
        instance.delete()

    def _update_account_balance(self, transaction):
        account = transaction.account
        if transaction.transaction_type == 'income':
            account.balance += transaction.amount
        elif transaction.transaction_type == 'expense':
            account.balance -= transaction.amount
        elif transaction.transaction_type == 'transfer':
            account.balance -= transaction.amount
            if transaction.to_account:
                to_account = transaction.to_account
                to_account.balance += transaction.amount
                to_account.save()
        account.save()

    def _revert_account_balance(self, transaction):
        account = transaction.account
        if transaction.transaction_type == 'income':
            account.balance -= transaction.amount
        elif transaction.transaction_type == 'expense':
            account.balance += transaction.amount
        elif transaction.transaction_type == 'transfer':
            account.balance += transaction.amount
            if transaction.to_account:
                to_account = transaction.to_account
                to_account.balance -= transaction.amount
                to_account.save()
        account.save()

    @action(detail=False, methods=['get'])
    def daily_summary(self, request):
        """按日汇总"""
        queryset = self.get_queryset().exclude(account__exclude_from_reports=True)
        year = int(request.query_params.get('year', datetime.now().year))
        month = int(request.query_params.get('month', datetime.now().month))
        queryset = queryset.filter(date__year=year, date__month=month)

        summary = queryset.values('date').annotate(
            income=Sum('amount', filter=Q(transaction_type='income'), default=0),
            expense=Sum('amount', filter=Q(transaction_type='expense'), default=0),
            count=Count('id'),
        ).order_by('date')

        data = DailySummarySerializer(
            [{'date': s['date'], 'income': s['income'], 'expense': s['expense'], 'count': s['count']} for s in summary],
            many=True
        ).data
        return Response(data)

    @action(detail=False, methods=['get'])
    def monthly_summary(self, request):
        """按月汇总"""
        queryset = self.get_queryset().exclude(account__exclude_from_reports=True)
        year = int(request.query_params.get('year', datetime.now().year))
        queryset = queryset.filter(date__year=year)

        summary = queryset.annotate(month=TruncMonth('date')).values('month').annotate(
            income=Sum('amount', filter=Q(transaction_type='income'), default=0),
            expense=Sum('amount', filter=Q(transaction_type='expense'), default=0),
        ).order_by('month')

        data = []
        for s in summary:
            income = s['income'] or 0
            expense = s['expense'] or 0
            data.append({
                'month': s['month'].strftime('%Y-%m'),
                'income': income,
                'expense': expense,
                'balance': income - expense,
            })
        return Response(MonthlySummarySerializer(data, many=True).data)

    @action(detail=False, methods=['get'])
    def category_summary(self, request):
        """按分类汇总"""
        queryset = self.get_queryset().exclude(account__exclude_from_reports=True)
        transaction_type = request.query_params.get('transaction_type', 'expense')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        year = request.query_params.get('year')
        month = request.query_params.get('month')

        queryset = queryset.filter(transaction_type=transaction_type)
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        if year:
            queryset = queryset.filter(date__year=int(year))
        if month:
            queryset = queryset.filter(date__month=int(month))

        summary = queryset.values('category__id', 'category__name', 'category__icon').annotate(
            total=Sum('amount', default=0),
            count=Count('id'),
        ).order_by('-total')

        data = CategorySummarySerializer(
            [{
                'category_id': s['category__id'],
                'category_name': s['category__name'] or '未分类',
                'category_icon': s['category__icon'] or '',
                'total': s['total'],
                'count': s['count'],
            } for s in summary],
            many=True
        ).data
        return Response(data)

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """仪表盘数据"""
        today = datetime.now().date()
        month_start = today.replace(day=1)
        queryset = self.get_queryset().exclude(account__exclude_from_reports=True)

        # 本月数据
        month_data = queryset.filter(date__gte=month_start).aggregate(
            income=Sum('amount', filter=Q(transaction_type='income'), default=0),
            expense=Sum('amount', filter=Q(transaction_type='expense'), default=0),
        )
        month_income = month_data['income'] or 0
        month_expense = month_data['expense'] or 0

        # 今日数据
        today_data = queryset.filter(date=today).aggregate(
            income=Sum('amount', filter=Q(transaction_type='income'), default=0),
            expense=Sum('amount', filter=Q(transaction_type='expense'), default=0),
        )

        # 最近交易
        recent = queryset[:10]

        # 账户总余额
        total_balance = sum(a.balance for a in request.user.accounts.filter(is_active=True, exclude_from_reports=False))

        return Response({
            'month_income': month_income,
            'month_expense': month_expense,
            'month_balance': month_income - month_expense,
            'today_income': today_data['income'] or 0,
            'today_expense': today_data['expense'] or 0,
            'total_balance': total_balance,
            'recent_transactions': TransactionSerializer(recent, many=True).data,
            # 预算数据
            'budgets': BudgetSerializer(
                Budget.objects.filter(user=request.user, is_active=True, year=today.year, month=today.month),
                many=True,
            ).data,
        })


class BudgetViewSet(viewsets.ModelViewSet):
    serializer_class = BudgetSerializer
    filterset_fields = ['category', 'period', 'year', 'month', 'is_active']

    def get_queryset(self):
        return Budget.objects.filter(user=self.request.user).select_related('category')

    def perform_create(self, serializer):
        today = datetime.now().date()
        serializer.save(user=self.request.user, year=today.year, month=today.month)

