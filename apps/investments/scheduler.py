import logging
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
from django.conf import settings

logger = logging.getLogger(__name__)

_scheduler = None


def _update_stock_prices_job():
    """定时任务：自动获取股票价格并更新"""
    import django
    django.setup()
    from .management.commands.update_stock_prices import is_trading_day, run_price_update
    from datetime import date

    today = date.today()
    if not is_trading_day(today):
        logger.info(f'{today} 非交易日，跳过自动更新')
        return

    logger.info('定时任务：开始更新股票价格...')
    try:
        updated, total, failed = run_price_update()
        msg = f'定时任务完成: {updated}/{total} 更新成功'
        if failed:
            msg += f'，{len(failed)} 个失败'
        logger.info(msg)
    except Exception as e:
        logger.error(f'定时任务异常: {e}', exc_info=True)


def start_scheduler():
    """启动定时任务调度器"""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(timezone='Asia/Shanghai')

    # 工作日 16:00（A 股 15:00 收盘后）自动更新价格
    _scheduler.add_job(
        _update_stock_prices_job,
        'cron',
        day_of_week='mon-fri',
        hour=16,
        minute=5,
        id='update_stock_prices',
        replace_existing=True,
    )

    _scheduler.start()
    atexit.register(_shutdown)
    logger.info('定时任务已启动：工作日 16:05 自动更新股票价格')


def _shutdown():
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
