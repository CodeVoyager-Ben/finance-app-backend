import os
import logging
import requests
from curl_cffi import requests as cffi_requests

logger = logging.getLogger(__name__)

SEARCH_URL = 'https://searchapi.eastmoney.com/api/suggest/get'
SEARCH_PARAMS = {
    'type': '14',
    'token': os.environ.get('EASTMONEY_SEARCH_TOKEN', ''),
    'count': '10',
}

TENCENT_QUOTE_URL = 'https://qt.gtimg.cn/q='


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


# ─── 实时行情获取（腾讯财经 API） ─────────────────────────────────────


def _symbol_to_tencent(symbol):
    """将 A 股代码转换为腾讯行情前缀格式"""
    if not symbol or not symbol.isdigit() or len(symbol) != 6:
        return None
    if symbol[0] == '6':
        return f'sh{symbol}'
    return f'sz{symbol}'


def _parse_tencent_quote(raw_text):
    """
    解析腾讯行情返回数据。
    字段: [1]名称 [3]最新价 [4]昨收 [32]涨跌额 [33]涨幅%
    """
    try:
        start = raw_text.index('"') + 1
        end = raw_text.rindex('"')
        parts = raw_text[start:end].split('~')
        if len(parts) < 35:
            return None
        name = parts[1]
        current_price = float(parts[3])
        previous_close = float(parts[4])
        if current_price <= 0:
            return None
        return {
            'name': name,
            'current_price': current_price,
            'previous_close': previous_close,
        }
    except (ValueError, IndexError):
        return None


def fetch_batch_prices(symbols):
    """
    批量获取股票最新价格。
    腾讯 API 支持逗号分隔批量查询，单次最多约 50 只。
    返回 {symbol: {'current_price', 'previous_close', 'name'}} 字典。
    """
    result = {}
    tencent_map = {}
    for s in symbols:
        tc = _symbol_to_tencent(s)
        if tc:
            tencent_map[tc] = s

    if not tencent_map:
        return result

    codes = list(tencent_map.keys())
    # 腾讯 API 支持逗号分隔批量查询
    batch = ','.join(codes)

    try:
        resp = requests.get(TENCENT_QUOTE_URL + batch, timeout=15)
        if resp.status_code != 200:
            raise Exception(f'HTTP {resp.status_code}')

        for line in resp.text.strip().split(';'):
            line = line.strip()
            if not line or '=' not in line:
                continue
            # 格式: v_sh600519="..."
            key = line.split('=')[0].strip().replace('v_', '')
            symbol = tencent_map.get(key)
            if not symbol:
                continue
            info = _parse_tencent_quote(line)
            if info and info['current_price']:
                result[symbol] = {
                    'current_price': info['current_price'],
                    'previous_close': info['previous_close'],
                    'name': info['name'],
                }
    except Exception as e:
        logger.warning(f'批量获取价格失败: {e}')

    logger.info(f'批量获取价格完成: {len(result)}/{len(symbols)} 成功')
    return result
