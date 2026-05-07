from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken
from apps.transactions.models import Account, Category
from apps.investments.models import AssetType
from django.contrib.auth import get_user_model

User = get_user_model()


class BaseTestCase(TestCase):
    """基础测试类：提供通用 setup 和工厂方法"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser', password='TestPass123!',
            email='test@example.com',
        )
        self.token = str(AccessToken.for_user(self.user))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token}')

        self.user2 = User.objects.create_user(
            username='testuser2', password='TestPass123!',
            email='test2@example.com',
        )

    def create_account(self, **kwargs):
        defaults = {
            'user': self.user, 'name': '测试账户', 'account_type': 'cash',
            'balance': 1000, 'icon': '💵', 'color': '#1677ff',
        }
        defaults.update(kwargs)
        return Account.objects.create(**defaults)

    def create_category(self, **kwargs):
        defaults = {
            'user': self.user, 'name': '测试分类', 'category_type': 'expense',
            'icon': '📌', 'color': '#1677ff', 'sort_order': 0,
        }
        defaults.update(kwargs)
        return Category.objects.create(**defaults)

    def get_asset_type(self):
        at, _ = AssetType.objects.get_or_create(
            code='stock', user=None,
            defaults={'name': '股票', 'category': 'security', 'icon': '📈', 'color': '#1677ff'},
        )
        return at
