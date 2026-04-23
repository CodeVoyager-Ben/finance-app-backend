import logging
from curl_cffi import requests as cffi_requests
import requests as std_requests

logger = logging.getLogger(__name__)

SEARCH_URL = 'https://searchapi.eastmoney.com/api/suggest/get'
SEARCH_PARAMS = {
    'type': '14',
    'token': 'D43BF722C8E33BDC906FB84D85E326E8',
    'count': '10',
}

KLINE_URL = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
KLINE_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://quote.eastmoney.com/',
}


def _classify_type(type_name):
    if not type_name:
        return 'stock'
    if any(k in type_name for k in ['基金', 'ETF', 'LOF']):
        return 'fund'
    if '债' in type_name:
        return 'bond'
    if '期货' in type_name:
        return 'futures'
    if '币' in type_name:
        return 'crypto'
    return 'stock'


def _search_eastmoney(keyword):
    """通过东方财富搜索 API 查询证券"""
    try:
        resp = cffi_requests.get(
            SEARCH_URL,
            params={**SEARCH_PARAMS, 'input': keyword},
            impersonate='chrome',
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('QuotationCodeTable', {}).get('Data', [])
            results = []
            for item in items[:10]:
                results.append({
                    'symbol': item.get('Code', ''),
                    'name': item.get('Name', ''),
                    'type': _classify_type(item.get('SecurityTypeName', '')),
                })
            return results
    except Exception as e:
        logger.warning(f'东方财富搜索失败: {e}')
    return []


def _search_akshare(code):
    """通过 AkShare 查询单只股票信息（fallback）"""
    try:
        from .proxy_pool import setup_proxy_env, clear_proxy_env
        setup_proxy_env()
        import akshare as ak
        info = ak.stock_individual_info_em(symbol=code)
        if not info.empty:
            name_row = info[info['item'] == '股票简称']
            price_row = info[info['item'] == '最新']
            name = name_row['value'].values[0] if not name_row.empty else ''
            price = float(price_row['value'].values[0]) if not price_row.empty else None
            if name:
                return [{
                    'symbol': code,
                    'name': name,
                    'price': price,
                    'type': 'stock',
                }]
    except Exception as e:
        logger.warning(f'AkShare 查询失败: {e}')
    finally:
        from .proxy_pool import clear_proxy_env
        clear_proxy_env()
    return []


def search_security(keyword):
    """搜索证券，返回 [{symbol, name, price, type}]"""
    if not keyword or len(keyword) < 1:
        return []

    results = _search_eastmoney(keyword)
    if results:
        return results

    if keyword.isdigit() and len(keyword) == 6:
        return _search_akshare(keyword)

    return []


# ─── 实时行情获取 ────────────────────────────────────────────────

def _symbol_to_secid(symbol):
    """将 A 股代码转换为东方财富 secid 格式"""
    if not symbol or not symbol.isdigit() or len(symbol) != 6:
        return None
    if symbol[0] == '6':
        return f'1.{symbol}'  # 沪市
    return f'0.{symbol}'      # 深市 / 北交所


def _request_with_proxy_fallback(method, url, **kwargs):
    """
    先尝试代理，失败后直连。
    返回 Response 或 None。
    """
    from .proxy_pool import get_proxies_dict, _cache_lock, _proxy_cache

    proxies = get_proxies_dict()
    timeout = kwargs.pop('timeout', 10)

    # 第一次尝试：使用代理
    if proxies:
        try:
            resp = method(url, proxies=proxies, timeout=timeout, **kwargs)
            if resp.status_code == 200:
                return resp
        except Exception as e:
            logger.warning(f'代理请求失败，切换直连: {e}')
            # 代理失败，清除缓存
            with _cache_lock:
                _proxy_cache['proxy'] = None

    # 第二次尝试：直连
    try:
        resp = method(url, timeout=timeout, **kwargs)
        if resp.status_code == 200:
            return resp
    except Exception as e:
        logger.warning(f'直连请求也失败: {e}')

    return None


def fetch_latest_price(symbol):
    """
    获取单只 A 股最新价格（通过东方财富 kline API）。
    先尝试代理，失败后直连。
    返回 {'symbol', 'name', 'current_price', 'previous_close'} 或 None。
    """
    secid = _symbol_to_secid(symbol)
    if not secid:
        return None

    resp = _request_with_proxy_fallback(
        std_requests.get,
        KLINE_URL,
        params={
            'secid': secid,
            'fields1': 'f1,f2,f3,f4,f5,f6',
            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
            'klt': '101',
            'fqt': '1',
            'end': '20500101',
            'lmt': '1',
        },
        headers=KLINE_HEADERS,
    )

    if resp:
        data = resp.json().get('data', {})
        if data and data.get('klines'):
            kline = data['klines'][-1].split(',')
            current_price = float(kline[2])
            previous_close = data.get('preKPrice')
            if previous_close:
                previous_close = float(previous_close)

            return {
                'symbol': data.get('code', symbol),
                'name': data.get('name', ''),
                'current_price': current_price,
                'previous_close': previous_close,
            }

    logger.warning(f'获取 {symbol} 价格失败（代理和直连均不可用）')
    return None


def _fetch_price_akshare(symbol):
    """通过 AkShare 获取股票价格（fallback）"""
    try:
        from .proxy_pool import setup_proxy_env, clear_proxy_env
        setup_proxy_env()
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == symbol]
        if row.empty:
            return None
        row = row.iloc[0]
        return {
            'symbol': symbol,
            'name': str(row.get('名称', '')),
            'current_price': float(row['最新价']) if row['最新价'] else None,
            'previous_close': float(row['昨收']) if row.get('昨收') else None,
        }
    except Exception as e:
        logger.warning(f'AkShare 获取 {symbol} 价格失败: {e}')
        return None
    finally:
        from .proxy_pool import clear_proxy_env
        clear_proxy_env()


def fetch_batch_prices(symbols):
    """
    批量获取股票最新价格。
    返回 {symbol: {'current_price', 'previous_close', 'name'}} 字典。
    """
    result = {}
    for symbol in symbols:
        price_info = fetch_latest_price(symbol)
        if price_info and price_info.get('current_price'):
            result[symbol] = {
                'current_price': price_info['current_price'],
                'previous_close': price_info.get('previous_close'),
                'name': price_info.get('name', ''),
            }
    logger.info(f'批量获取价格完成: {len(result)}/{len(symbols)} 成功')
    return result
