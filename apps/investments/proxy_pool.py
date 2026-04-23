import os
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

logger = logging.getLogger(__name__)

_cache_lock = threading.Lock()
_proxy_cache = {'proxy': None, 'expires': 0, 'type': None}
CACHE_TTL = 300

TEST_URL = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
TEST_PARAMS = {
    'secid': '1.600519',
    'fields1': 'f1',
    'fields2': 'f51,f52',
    'klt': '101', 'fqt': '1', 'end': '20500101', 'lmt': '1',
}
TEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://quote.eastmoney.com/',
}
TEST_TIMEOUT = 8
MAX_WORKERS = 10

# GitHub 免费代理列表（通过 ghfast.top 镜像）
GITHUB_PROXY_SOURCES = [
    'https://ghfast.top/https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
    'https://ghfast.top/https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt',
    'https://ghfast.top/https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt',
]

# 备用代理 API
PROXY_API_URLS = [
    'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all',
]


def _test_proxy(proxy_url):
    """校验代理 IP 是否可用（请求东方财富 API 验证）"""
    try:
        r = requests.get(
            TEST_URL,
            params=TEST_PARAMS,
            headers=TEST_HEADERS,
            proxies={'http': proxy_url, 'https': proxy_url},
            timeout=TEST_TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json().get('data', {})
            if data and data.get('klines'):
                return True
    except Exception:
        pass
    return False


def _fetch_proxy_list():
    """从多个源获取代理列表"""
    all_proxies = []

    for url in GITHUB_PROXY_SOURCES:
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                for line in resp.text.strip().split('\n'):
                    addr = line.strip()
                    if not addr or ':' not in addr:
                        continue
                    if addr.startswith('http'):
                        all_proxies.append(addr)
                    elif addr.startswith('socks'):
                        all_proxies.append(addr)
                    else:
                        all_proxies.append(f'http://{addr}')
        except Exception as e:
            logger.debug(f'代理源 {url} 获取失败: {e}')

    for url in PROXY_API_URLS:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                for line in resp.text.strip().split('\n'):
                    addr = line.strip()
                    if addr:
                        all_proxies.append(f'http://{addr}')
        except Exception as e:
            logger.debug(f'代理 API {url} 失败: {e}')

    # 去重
    return list(set(all_proxies))


def _find_working_proxy(proxy_list, max_test=50):
    """并行校验代理列表，返回第一个可用的"""
    candidates = proxy_list[:max_test]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_test_proxy, p): p for p in candidates}
        for future in as_completed(futures):
            proxy = futures[future]
            try:
                if future.result():
                    logger.info(f'找到可用代理: {proxy}')
                    return proxy
            except Exception:
                continue
    return None


def _fetch_from_free_proxy_lib():
    """通过 free-proxy 库获取"""
    try:
        from fp.fp import FreeProxy
        for _ in range(5):
            proxy = FreeProxy(timeout=TEST_TIMEOUT, rand=True).get()
            if proxy and _test_proxy(proxy):
                logger.info(f'FreeProxy 可用: {proxy}')
                return proxy
    except Exception as e:
        logger.debug(f'FreeProxy 失败: {e}')
    return None


def get_proxy():
    """
    获取一个可用的代理 IP（带缓存）。
    先校验缓存的代理，不可用则从代理列表并行校验获取新代理。
    """
    with _cache_lock:
        now = time.time()
        if _proxy_cache['proxy'] and now < _proxy_cache['expires']:
            if _test_proxy(_proxy_cache['proxy']):
                return _proxy_cache['proxy']
            _proxy_cache['proxy'] = None

    # 手动配置优先
    try:
        from django.conf import settings
        manual = getattr(settings, 'STOCK_PROXY', None)
        if manual:
            if _test_proxy(manual):
                with _cache_lock:
                    _proxy_cache['proxy'] = manual
                    _proxy_cache['expires'] = now + CACHE_TTL
                return manual
            logger.warning('手动配置的代理不可用')
    except Exception:
        pass

    # 获取代理列表并并行校验
    proxy_list = _fetch_proxy_list()
    logger.info(f'获取到 {len(proxy_list)} 个代理候选')
    proxy = _find_working_proxy(proxy_list)

    # 兜底: free-proxy 库
    if not proxy:
        proxy = _fetch_from_free_proxy_lib()

    if proxy:
        with _cache_lock:
            _proxy_cache['proxy'] = proxy
            _proxy_cache['expires'] = now + CACHE_TTL
        return proxy

    logger.warning('未获取到可用代理，将直连')
    return None


def get_proxies_dict():
    """返回 requests 库用的 proxies 字典，无代理时返回 None"""
    proxy = get_proxy()
    if proxy:
        return {'http': proxy, 'https': proxy}
    return None


def setup_proxy_env():
    """设置环境变量代理（供 AkShare 等使用环境变量的库）"""
    proxy = get_proxy()
    if proxy:
        os.environ['http_proxy'] = proxy
        os.environ['https_proxy'] = proxy
        return True
    else:
        clear_proxy_env()
        return False


def clear_proxy_env():
    """清除环境变量代理"""
    os.environ.pop('http_proxy', None)
    os.environ.pop('https_proxy', None)
