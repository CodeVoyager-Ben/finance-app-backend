import re
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'avatar', 'currency', 'date_joined']
        read_only_fields = ['id', 'date_joined']


def validate_password_strength(password):
    """密码强度校验：至少8位，包含大小写字母、数字和特殊字符中的至少3种"""
    if len(password) < 8:
        raise serializers.ValidationError('密码长度不能少于8位')

    checks = [
        (re.search(r'[a-z]', password), '小写字母'),
        (re.search(r'[A-Z]', password), '大写字母'),
        (re.search(r'\d', password), '数字'),
        (re.search(r'[!@#$%^&*()_+\-=\[\]{};\'\\:"|,<.>/?`~]', password), '特殊字符'),
    ]

    passed = sum(1 for check, _ in checks if check)
    if passed < 3:
        names = [name for check, name in checks if not check]
        raise serializers.ValidationError(
            f'密码强度不足，需包含大写字母、小写字母、数字、特殊字符中的至少3种。'
            f' 建议补充：{"、".join(names)}'
        )

    # 不能和用户名太相似（在 RegisterSerializer 中做上下文校验）
    return password


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'password', 'email', 'phone']

    def validate_password(self, value):
        validate_password_strength(value)
        return value

    def validate(self, attrs):
        # 密码不能包含用户名
        username = attrs.get('username', '')
        password = attrs.get('password', '')
        if username.lower() in password.lower():
            raise serializers.ValidationError({'password': '密码不能包含用户名'})
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)

    def validate_new_password(self, value):
        validate_password_strength(value)
        return value
