from django.apps import AppConfig


class InvestmentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.investments'
    verbose_name = '投资管理'

    def ready(self):
        from django.conf import settings
        if getattr(settings, 'AUTO_UPDATE_STOCK_PRICES', False):
            import os
            # 避免在 manage.py 子进程（如 migrate）中重复启动
            if os.environ.get('RUN_MAIN') == 'true' or 'gunicorn' in __import__('sys').argv[0]:
                from .scheduler import start_scheduler
                start_scheduler()
