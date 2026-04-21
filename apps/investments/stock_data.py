import logging
from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

SEARCH_URL = 'https://searchapi.eastmoney.com/api/suggest/get'
SEARCH_PARAMS = {
    'type': '14',
    'token': 'D43BF722C8E33BDC906FB84D85E326E8',
    'count': '10',
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

    # 优先东方财富搜索（快速、支持代码和名称模糊搜索）
    results = _search_eastmoney(keyword)
    if results:
        return results

    # 搜索无结果时，尝试 AkShare（仅 6 位数字代码）
    if keyword.isdigit() and len(keyword) == 6:
        return _search_akshare(keyword)

    return []
