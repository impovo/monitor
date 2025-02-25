#!/usr/bin/env python3
import requests
import time
import logging
import json

# ---------------- 配置参数 ----------------
# 企业微信 Bot 的 Webhook 地址（请替换为你自己的）
WECHAT_BOT_URL = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=0213d575-5764-44f3-83a1-2c64ccafd3f5'

# 日志设置（同时输出到控制台和日志文件）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("monitor.log", encoding="utf-8")
    ]
)

# 用于记录上一次获取的持仓和价格数据（方便比较百分比变化）
state = {
    'binance': {},
    'okx': {},
    'bybit': {}
}

# 用于记录已经推送过的代币（避免重复推送）
pushed_symbols = set()

# ---------------- 企业微信推送函数 ----------------
def send_wechat_message(message):
    data = {
        "msgtype": "text",
        "text": {"content": message}
    }
    try:
        resp = requests.post(WECHAT_BOT_URL, json=data, timeout=5)
        if resp.status_code != 200:
            logging.error(f"发送微信消息失败: {resp.text}")
    except Exception as e:
        logging.error(f"发送微信消息异常: {e}")

# ---------------- 币安 API 相关函数 ----------------
def get_binance_symbols():
    """
    获取币安永续合约交易对列表
    """
    url = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        symbols = []
        for info in data.get('symbols', []):
            # 只选择永续合约且交易状态正常的品种
            if info.get('contractType') == 'PERPETUAL' and info.get('status') == 'TRADING':
                symbols.append(info['symbol'])
        return symbols
    except Exception as e:
        logging.error(f"获取币安 symbol 列表异常: {e}")
        return []

def get_binance_funding_rate(symbol):
    """
    获取币安当前资金费率（返回百分比）
    """
    url = f'https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if isinstance(data, list) and len(data) > 0:
            rate = float(data[0].get('fundingRate', 0))
            return rate * 100  # 转换为百分比
    except Exception as e:
        logging.error(f"获取币安 {symbol} 资金费率异常: {e}")
    return None

def get_binance_open_interest(symbol):
    """
    获取币安合约持仓量
    """
    url = f'https://fapi.binance.com/fapi/v1/openInterest?symbol={symbol}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if 'openInterest' in data:
            return float(data['openInterest'])
    except Exception as e:
        logging.error(f"获取币安 {symbol} 持仓量异常: {e}")
    return None

def get_binance_price(symbol):
    """
    获取币安最新价格
    """
    url = f'https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if 'price' in data:
            return float(data['price'])
    except Exception as e:
        logging.error(f"获取币安 {symbol} 价格异常: {e}")
    return None

# ---------------- OKX API 相关函数 ----------------
def get_okx_symbols():
    """
    获取 OKX 永续掉期交易对列表
    """
    url = 'https://www.okx.com/api/v5/public/instruments?instType=SWAP'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        symbols = []
        if data.get('code') == '0':
            for inst in data.get('data', []):
                symbols.append(inst['instId'])
        return symbols
    except Exception as e:
        logging.error(f"获取 OKX symbol 列表异常: {e}")
        return []

def get_okx_funding_rate(instId):
    """
    获取 OKX 资金费率（返回百分比）
    """
    url = f'https://www.okx.com/api/v5/public/funding-rate?instId={instId}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('code') == '0' and data.get('data'):
            rate = float(data['data'][0].get('fundingRate', 0))
            return rate * 100
    except Exception as e:
        logging.error(f"获取 OKX {instId} 资金费率异常: {e}")
    return None

def get_okx_open_interest(instId):
    """
    获取 OKX 持仓量
    """
    url = f'https://www.okx.com/api/v5/public/open-interest?instId={instId}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('code') == '0' and data.get('data'):
            return float(data['data'][0].get('oi', 0))
    except Exception as e:
        logging.error(f"获取 OKX {instId} 持仓量异常: {e}")
    return None

def get_okx_price(instId):
    """
    获取 OKX 最新价格
    """
    url = f'https://www.okx.com/api/v5/market/ticker?instId={instId}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('code') == '0' and data.get('data'):
            return float(data['data'][0].get('last', 0))
    except Exception as e:
        logging.error(f"获取 OKX {instId} 价格异常: {e}")
    return None

# ---------------- Bybit API 相关函数 ----------------
def get_bybit_symbols():
    """
    获取 Bybit 交易对列表
    """
    url = 'https://api.bybit.com/v2/public/symbols'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        symbols = []
        if data.get('ret_code') == 0:
            for info in data.get('result', []):
                if info.get('name'):
                    symbols.append(info['name'])
        return symbols
    except Exception as e:
        logging.error(f"获取 Bybit symbol 列表异常: {e}")
    return []

def get_bybit_funding_rate(symbol):
    """
    获取 Bybit 资金费率（返回百分比）
    """
    url = f'https://api.bybit.com/v2/public/funding/prev-funding-rate?symbol={symbol}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('ret_code') == 0 and data.get('result'):
            rate = float(data['result'].get('funding_rate', 0))
            return rate * 100
    except Exception as e:
        logging.error(f"获取 Bybit {symbol} 资金费率异常: {e}")
    return None

def get_bybit_open_interest(symbol):
    """
    获取 Bybit 持仓量（部分接口版本可能有所不同）
    """
    url = f'https://api.bybit.com/v2/public/open-interest?symbol={symbol}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('ret_code') == 0 and data.get('result'):
            return float(data['result'].get('open_interest', 0))
    except Exception as e:
        logging.error(f"获取 Bybit {symbol} 持仓量异常: {e}")
    return None

def get_bybit_price(symbol):
    """
    获取 Bybit 最新价格
    """
    url = f'https://api.bybit.com/v2/public/tickers?symbol={symbol}'
    try:
        resp = requests.get(url, timeout=10)
        data = resp.json()
        if data.get('ret_code') == 0 and data.get('result'):
            return float(data['result'][0].get('last_price', 0))
    except Exception as e:
        logging.error(f"获取 Bybit {symbol} 价格异常: {e}")
    return None

# ---------------- 主监控循环 ----------------
def monitor_exchange(exchange, symbols_func, funding_func, price_func, oi_func):
    symbols = symbols_func()
    logging.info(f"{exchange}监控交易对数：{len(symbols)}")
    for symbol in symbols:
        if symbol in pushed_symbols:
            continue  # 跳过已经推送过的代币

        # 获取价格和资金费率
        price = price_func(symbol)
        funding_rate = funding_func(symbol)
        oi = oi_func(symbol)

        # 资金费率检测
        if funding_rate is not None and funding_rate < -1:
            msg = f"[{exchange}] {symbol} 资金费率告警：{funding_rate:.2f}% (< -1%)"
            logging.info(msg)
            send_wechat_message(msg)

        # 1分钟价格涨幅超过10%检测
        if price is not None:
            prev_price = state[exchange].get(symbol, {}).get('price')
            if prev_price is not None and prev_price > 0:
                change = ((price - prev_price) / prev_price) * 100
                if change > 10:
                    msg = f"[{exchange}] {symbol} 1 分钟内价格上涨 {change:.2f}%（{prev_price} -> {price}）"
                    logging.info(msg)
                    send_wechat_message(msg)

            # 更新代币价格
            if symbol not in state[exchange]:
                state[exchange][symbol] = {}
            state[exchange][symbol]['price'] = price

        # 合约持仓量检测（较上次增长超过 15%）
        if oi is not None:
            prev_oi = state[exchange].get(symbol, {}).get('oi')
            if prev_oi is not None and prev_oi > 0:
                change = ((oi - prev_oi) / prev_oi) * 100
                if change > 15:
                    msg = f"[{exchange}] {symbol} 持仓量增长 {change:.2f}%（{prev_oi} -> {oi}）"
                    logging.info(msg)
                    send_wechat_message(msg)

            # 更新合约持仓量
            state[exchange][symbol]['oi'] = oi

        # 标记该代币已推送
        pushed_symbols.add(symbol)

# ---------------- 启动程序 ----------------
def main():
    logging.info("启动监控程序……")
    while True:
        try:
            monitor_exchange("币安", get_binance_symbols, get_binance_funding_rate, get_binance_price, get_binance_open_interest)
        except Exception as e:
            logging.error(f"币安监控异常: {e}")

        try:
            monitor_exchange("OKX", get_okx_symbols, get_okx_funding_rate, get_okx_price, get_okx_open_interest)
        except Exception as e:
            logging.error(f"OKX监控异常: {e}")

        try:
            monitor_exchange("Bybit", get_bybit_symbols, get_bybit_funding_rate, get_bybit_price, get_bybit_open_interest)
        except Exception as e:
            logging.error(f"Bybit监控异常: {e}")

        # 每 60 秒检测一次
        time.sleep(60)

if __name__ == '__main__':
    main()
