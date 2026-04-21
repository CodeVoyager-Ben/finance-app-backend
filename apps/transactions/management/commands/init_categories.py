from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.transactions.models import Category

User = get_user_model()

# 预置分类数据 - 参考随手记分类体系
EXPENSE_CATEGORIES = [
    ('餐饮', '🍜', '#ff6b6b', [
        ('早餐', '🥞'), ('午餐', '🍱'), ('晚餐', '🍲'), ('外卖', '🛵'),
        ('奶茶零食', '🧋'), ('聚餐', '🍻'), ('水果', '🍇'),
    ]),
    ('交通', '🚗', '#4ecdc4', [
        ('公交地铁', '🚇'), ('打车', '🚕'), ('共享单车', '🚲'), ('加油', '⛽'),
        ('停车费', '🅿️'), ('过路费', '🛣️'), ('火车飞机', '✈️'),
    ]),
    ('购物', '🛒', '#ff9a56', [
        ('日用品', '🧴'), ('衣服鞋帽', '👗'), ('数码电子', '📱'), ('护肤美容', '💄'),
        ('家居家装', '🏠'), ('家电', '📺'),
    ]),
    ('居住', '🏠', '#7c5cfc', [
        ('房租', '🏘️'), ('房贷', '🏦'), ('水电燃气', '💡'), ('物业费', '🏢'),
        ('装修维修', '🔨'), ('网费', '🌐'),
    ]),
    ('娱乐', '🎮', '#ff6b9d', [
        ('电影', '🎬'), ('游戏', '🎯'), ('旅游', '✈️'), ('运动健身', '🏋️'),
        ('足球', '⚽'), ('KTV', '🎤'), ('会员订阅', '💎'),
    ]),
    ('医疗', '💊', '#2ecc71', [
        ('门诊', '🏥'), ('药品', '💊'), ('体检', '🩺'), ('牙科', '🦷'),
        ('保健养生', '🧘'),
    ]),
    ('教育', '📚', '#3498db', [
        ('书籍', '📖'), ('培训课程', '🎓'), ('学费', '🎒'), ('考试', '📝'),
    ]),
    ('通讯', '📱', '#1abc9c', [
        ('手机话费', '📞'), ('宽带', '📶'),
    ]),
    ('人情', '🎁', '#e74c3c', [
        ('红包', '🧧'), ('礼物', '🎁'), ('请客', '🍽️'), ('份子钱', '💰'),
    ]),
    ('亲子', '👶', '#f39c12', [
        ('奶粉尿布', '🍼'), ('玩具', '🧸'), ('早教', '🧒'), ('学费', '🎒'),
    ]),
    ('宠物', '🐾', '#e67e22', [
        ('宠物食品', '🍖'), ('宠物医疗', '🏥'), ('宠物用品', '🦴'),
    ]),
    ('其他支出', '📌', '#95a5a6', [
        ('杂费', '🧾'), ('罚款', '⚖️'), ('捐赠', '❤️'),
    ]),
    ('还信用卡', '💳', '#722ed1', []),
]

INCOME_CATEGORIES = [
    ('工资收入', '💰', '#2ecc71', [
        ('工资', '💵'), ('奖金', '🎯'), ('加班费', '⏰'), ('绩效', '🏆'),
    ]),
    ('兼职收入', '💼', '#3498db', [
        ('兼职', '💼'), ('稿费', '✍️'), ('咨询', '🤝'), ('外包', '💻'),
    ]),
    ('投资收益', '📈', '#9b59b6', [
        ('股票', '📊'), ('基金', '📈'), ('利息', '🏦'), ('分红', '🪙'),
        ('虚拟货币', '₿'), ('期货', '📋'),
    ]),
    ('其他收入', '🎉', '#e67e22', [
        ('报销', '🧾'), ('礼金', '🧧'), ('中奖', '🎰'), ('退款', '↩️'),
        ('补贴', '📋'), ('二手转让', '🔄'), ('足球', '⚽'),
    ]),
]


class Command(BaseCommand):
    help = '为用户初始化预置分类数据'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='指定用户名（默认为所有用户）')

    def handle(self, *args, **options):
        username = options.get('username')
        if username:
            users = User.objects.filter(username=username)
        else:
            users = User.objects.all()

        for user in users:
            self._init_for_user(user)

    def _init_for_user(self, user):
        count = 0
        # 支出分类
        for i, (name, icon, color, children) in enumerate(EXPENSE_CATEGORIES):
            parent, created = Category.objects.get_or_create(
                user=user, name=name, category_type='expense', parent__isnull=True,
                defaults={'icon': icon, 'color': color, 'sort_order': i},
            )
            if created:
                count += 1
            for j, (child_name, child_icon) in enumerate(children):
                _, c = Category.objects.get_or_create(
                    user=user, name=child_name, category_type='expense', parent=parent,
                    defaults={'icon': child_icon, 'sort_order': j},
                )
                if c:
                    count += 1

        # 收入分类
        for i, (name, icon, color, children) in enumerate(INCOME_CATEGORIES):
            parent, created = Category.objects.get_or_create(
                user=user, name=name, category_type='income', parent__isnull=True,
                defaults={'icon': icon, 'color': color, 'sort_order': i},
            )
            if created:
                count += 1
            for j, (child_name, child_icon) in enumerate(children):
                _, c = Category.objects.get_or_create(
                    user=user, name=child_name, category_type='income', parent=parent,
                    defaults={'icon': child_icon, 'sort_order': j},
                )
                if c:
                    count += 1

        self.stdout.write(self.style.SUCCESS(f'用户 {user.username}: 初始化了 {count} 个分类'))
