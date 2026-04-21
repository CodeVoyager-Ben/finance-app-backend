from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, RegisterSerializer, ChangePasswordSerializer
from apps.transactions.management.commands.init_categories import (
    EXPENSE_CATEGORIES, INCOME_CATEGORIES,
)
from apps.transactions.models import Category, Account

User = get_user_model()


def init_default_data(user):
    """为新用户创建预置分类和默认账户"""
    # 支出分类
    for i, (name, icon, color, children) in enumerate(EXPENSE_CATEGORIES):
        parent = Category.objects.create(
            user=user, name=name, category_type='expense',
            icon=icon, color=color, sort_order=i,
        )
        for j, (child_name, child_icon) in enumerate(children):
            Category.objects.create(
                user=user, name=child_name, category_type='expense',
                parent=parent, icon=child_icon, sort_order=j,
            )
    # 收入分类
    for i, (name, icon, color, children) in enumerate(INCOME_CATEGORIES):
        parent = Category.objects.create(
            user=user, name=name, category_type='income',
            icon=icon, color=color, sort_order=i,
        )
        for j, (child_name, child_icon) in enumerate(children):
            Category.objects.create(
                user=user, name=child_name, category_type='income',
                parent=parent, icon=child_icon, sort_order=j,
            )
    # 默认账户
    Account.objects.create(user=user, name='现金', account_type='cash', icon='💵', color='#52c41a')
    Account.objects.create(user=user, name='微信钱包', account_type='wechat', icon='💚', color='#07c160')
    Account.objects.create(user=user, name='支付宝', account_type='alipay', icon='💙', color='#1677ff')
    Account.objects.create(user=user, name='银行卡', account_type='bank', icon='🏦', color='#722ed1')
    Account.objects.create(user=user, name='信用卡', account_type='credit_card', icon='💳', color='#ff4d4f')


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        init_default_data(user)
        return Response({
            'user': UserSerializer(user).data,
            'message': '注册成功'
        }, status=status.HTTP_201_CREATED)


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.UpdateAPIView):
    serializer_class = ChangePasswordSerializer

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.data['old_password']):
            return Response({'old_password': ['密码错误']}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(serializer.data['new_password'])
        user.save()
        return Response({'message': '密码修改成功'})
