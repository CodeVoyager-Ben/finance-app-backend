import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

_proxy_cache = {'proxy': None, 'expires': 0}
CACHE_TTL = 300

TEST_URL = 'http://push2.eastmoney.com/api/qt/stock/get?secid=1.000001&fields=f43'
TEST_TIMEOUT = 5

PROXY_API_URLS = [
    'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all',
]


def _test_proxy(proxy_url):
    try:
        resp = requests.get(
            TEST_URL,
            proxies={'http': proxy_url, 'https': proxy_url},
            timeout=TEST_TIMEOUT,
        )
        return resp.status_code == 200
    except Exception:
        return False


def _fetch_from_free_proxy_lib():
    try:
        from fp.fp import FreeProxy
        for _ in range(3):
            proxy = FreeProxy(timeout=TEST_TIMEOUT, rand=True).get()
            if proxy and _test_proxy(proxy):
                return proxy
    except Exception as e:
        logger.debug(f'FreeProxy 失败: {e}')
    return None


def _fetch_from_api():
    for url in PROXY_API_URLS:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                lines = resp.text.strip().split('\n')
                for line in lines[:10]:
                    addr = line.strip()
                    if addr:
                        proxy = f'http://{addr}'
                        if _test_proxy(proxy):
                            return proxy
        except Exception as e:
            logger.debug(f'代理 API {url} 失败: {e}')
    return None


def get_proxy():
    now = time.time()
    if _proxy_cache['proxy'] and now < _proxy_cache['expires']:
        return _proxy_cache['proxy']

    # 从 Django settings 读取手动配置的代理
    try:
        from django.conf import settings
        manual = getattr(settings, 'STOCK_PROXY', None)
        if manual:
            _proxy_cache['proxy'] = manual
            _proxy_cache['expires'] = now + CACHE_TTL
            return manual
    except Exception:
        pass

    # 尝试自动获取
    proxy = _fetch_from_api() or _fetch_from_free_proxy_lib()
    if proxy:
        _proxy_cache['proxy'] = proxy
        _proxy_cache['expires'] = now + CACHE_TTL
        logger.info(f'获取到可用代理: {proxy}')
        return proxy

    logger.warning('未获取到可用代理，将直连')
    return None


def setup_proxy_env():
    proxy = get_proxy()
    if proxy:
        os.environ['http_proxy'] = proxy
        os.environ['https_proxy'] = proxy
        return True
    else:
        clear_proxy_env()
        return False


def clear_proxy_env():
    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)
