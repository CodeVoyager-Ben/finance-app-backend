from django.contrib.auth import get_user_model
from tests.base import BaseTestCase
from apps.transactions.models import Account, Category

User = get_user_model()

REGISTER_URL = '/api/auth/register/'
LOGIN_URL = '/api/auth/login/'
PROFILE_URL = '/api/auth/profile/'
CHANGE_PASSWORD_URL = '/api/auth/change-password/'


class RegisterTests(BaseTestCase):
    """注册相关测试"""

    def test_register_success(self):
        """成功注册，返回用户数据，创建默认账户和分类"""
        data = {
            'username': 'newuser',
            'password': 'NewPass123!',
            'email': 'new@example.com',
        }
        response = self.client.post(REGISTER_URL, data)
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertIn('user', body)
        self.assertEqual(body['user']['username'], 'newuser')
        self.assertEqual(body['user']['email'], 'new@example.com')
        self.assertIn('message', body)

        user = User.objects.get(username='newuser')
        self.assertEqual(Account.objects.filter(user=user).count(), 5)
        self.assertTrue(Category.objects.filter(user=user).exists())

    def test_register_duplicate_username(self):
        """重复用户名注册失败"""
        data = {
            'username': 'testuser',
            'password': 'TestPass123!',
            'email': 'another@example.com',
        }
        response = self.client.post(REGISTER_URL, data)
        self.assertEqual(response.status_code, 400)

    def test_register_password_contains_username(self):
        """密码包含用户名时注册失败"""
        data = {
            'username': 'testuser',
            'password': 'testuser123!',
            'email': 'pw@example.com',
        }
        response = self.client.post(REGISTER_URL, data)
        self.assertEqual(response.status_code, 400)

    def test_register_password_too_short(self):
        """密码少于8位注册失败"""
        data = {
            'username': 'shortpw',
            'password': 'Ab1!',
            'email': 'short@example.com',
        }
        response = self.client.post(REGISTER_URL, data)
        self.assertEqual(response.status_code, 400)

    def test_register_password_weak(self):
        """密码缺少足够字符类别注册失败（仅小写字母）"""
        data = {
            'username': 'weakpw',
            'password': 'abcdefgh',
            'email': 'weak@example.com',
        }
        response = self.client.post(REGISTER_URL, data)
        self.assertEqual(response.status_code, 400)


class LoginTests(BaseTestCase):
    """登录相关测试"""

    def test_login_success(self):
        """成功登录返回 access 和 refresh 令牌"""
        self.client.credentials()
        data = {
            'username': 'testuser',
            'password': 'TestPass123!',
        }
        response = self.client.post(LOGIN_URL, data)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('access', body)
        self.assertIn('refresh', body)

    def test_login_wrong_password(self):
        """错误密码登录返回 401"""
        self.client.credentials()
        data = {
            'username': 'testuser',
            'password': 'WrongPass123!',
        }
        response = self.client.post(LOGIN_URL, data)
        self.assertEqual(response.status_code, 401)


class ProfileTests(BaseTestCase):
    """用户信息相关测试"""

    def test_get_profile(self):
        """获取当前用户信息"""
        response = self.client.get(PROFILE_URL)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['username'], 'testuser')
        self.assertEqual(body['email'], 'test@example.com')

    def test_update_profile(self):
        """更新用户邮箱"""
        data = {'email': 'updated@example.com'}
        response = self.client.patch(PROFILE_URL, data)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['email'], 'updated@example.com')
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, 'updated@example.com')


class ChangePasswordTests(BaseTestCase):
    """修改密码相关测试"""

    def test_change_password_success(self):
        """成功修改密码"""
        data = {
            'old_password': 'TestPass123!',
            'new_password': 'NewPass456!',
        }
        response = self.client.put(CHANGE_PASSWORD_URL, data)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn('message', body)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPass456!'))

    def test_change_password_wrong_old(self):
        """旧密码错误时修改失败"""
        data = {
            'old_password': 'WrongOld123!',
            'new_password': 'NewPass456!',
        }
        response = self.client.put(CHANGE_PASSWORD_URL, data)
        self.assertEqual(response.status_code, 400)
