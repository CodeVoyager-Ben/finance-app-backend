from rest_framework import serializers
from .models import Account, Category, Transaction, Budget


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'name', 'account_type', 'balance', 'icon', 'color', 'is_active', 'exclude_from_reports', 'created_at']
        read_only_fields = ['id', 'created_at']


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.name', read_only=True, default=None)

    class Meta:
        model = Category
        fields = ['id', 'name', 'category_type', 'icon', 'color', 'parent', 'parent_name', 'children', 'sort_order', 'is_active']
        read_only_fields = ['id']

    def get_children(self, obj):
        if hasattr(obj, '_children'):
            return CategorySerializer(obj._children, many=True).data
        children = obj.children.filter(is_active=True)
        return CategorySerializer(children, many=True).data


class TransactionSerializer(serializers.ModelSerializer):
    account_name = serializers.CharField(source='account.name', read_only=True)
    to_account_name = serializers.CharField(source='to_account.name', read_only=True, default='')
    category_name = serializers.CharField(source='category.name', read_only=True, default='')
    category_icon = serializers.CharField(source='category.icon', read_only=True, default='')

    class Meta:
        model = Transaction
        fields = [
            'id', 'account', 'account_name', 'to_account', 'to_account_name',
            'category', 'category_name', 'category_icon', 'transaction_type',
            'amount', 'note', 'date', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransactionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['account', 'to_account', 'category', 'transaction_type', 'amount', 'note', 'date']

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('金额必须大于0')
        return value


class DailySummarySerializer(serializers.Serializer):
    date = serializers.DateField()
    income = serializers.DecimalField(max_digits=15, decimal_places=2)
    expense = serializers.DecimalField(max_digits=15, decimal_places=2)
    count = serializers.IntegerField()


class MonthlySummarySerializer(serializers.Serializer):
    month = serializers.CharField()
    income = serializers.DecimalField(max_digits=15, decimal_places=2)
    expense = serializers.DecimalField(max_digits=15, decimal_places=2)
    balance = serializers.DecimalField(max_digits=15, decimal_places=2)


class CategorySummarySerializer(serializers.Serializer):
    category_id = serializers.IntegerField()
    category_name = serializers.CharField()
    category_icon = serializers.CharField()
    total = serializers.DecimalField(max_digits=15, decimal_places=2)
    count = serializers.IntegerField()


class BudgetSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True, default='总预算')
    category_icon = serializers.CharField(source='category.icon', read_only=True, default='💰')
    spent = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            'id', 'category', 'category_name', 'category_icon',
            'amount', 'period', 'year', 'month', 'is_active',
            'spent', 'remaining', 'percentage', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']

    def _get_spent(self, obj):
        from django.db.models import Sum
        qs = Transaction.objects.filter(
            user=obj.user, transaction_type='expense',
            date__year=obj.year, date__month=obj.month,
        ).exclude(account__exclude_from_reports=True)
        if obj.category:
            # 该分类及其子分类的支出
            cat_ids = [obj.category.id] + list(
                obj.category.children.values_list('id', flat=True)
            )
            qs = qs.filter(category_id__in=cat_ids)
        result = qs.aggregate(total=Sum('amount', default=0))
        return result['total']

    def get_spent(self, obj):
        return self._get_spent(obj)

    def get_remaining(self, obj):
        return float(obj.amount) - float(self._get_spent(obj))

    def get_percentage(self, obj):
        spent = float(self._get_spent(obj))
        if float(obj.amount) == 0:
            return 0
        return round(min(spent / float(obj.amount) * 100, 100), 1)
