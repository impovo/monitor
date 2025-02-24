import ccxt
import requests
import time
from datetime import datetime, timedelta

# 初始化交易所（公共API）
exchanges = {
    'binance': ccxt.binance({
        'timeout': 30000,  # 单位：毫秒（30秒）
    }),
    'bybit': ccxt.bybit({
        'timeout': 30000,
        'options': {'adjustForTimeDifference': True}
    }),
    'okx': ccxt.okx({
        'timeout': 30000
    })
}

# 动态获取所有永续合约交易对
def get_perpetual_symbols(exchange):
    max_retries = 3
    for _ in range(max_retries):
        try:
            markets = exchange.load_markets()
            perpetual_symbols = []
            for symbol in markets:
                market = markets[symbol]
                if exchange.id == 'binance' and market['swap'] and market['quote'] == 'USDT':
                    perpetual_symbols.append(symbol)
                elif exchange.id == 'bybit' and 'USDT' in symbol and ':USDT' in symbol:
                    perpetual_symbols.append(symbol)
                elif exchange.id == 'okx' and '-SWAP' in symbol:
                    perpetual_symbols.append(symbol)
            return perpetual_symbols
        except Exception as e:
            print(f"加载 {exchange.id} 市场失败，重试中... 错误：{e}")
            time.sleep(5)
    return []

# 初始化交易对列表
symbols_config = {
    ex_name: get_perpetual_symbols(ex) 
    for ex_name, ex in exchanges.items()
}

# 企业微信Webhook
WX_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=0213d575-5764-44f3-83a1-2c64ccafd3f5"

# 存储历史数据和状态
history = {ex: {} for ex in exchanges}  # 延迟初始化

def send_to_wx(msg):
    """推送Markdown消息到企业微信"""
    data = {"msgtype": "markdown", "markdown": {"content": msg}}
    requests.post(WX_WEBHOOK, json=data)

def monitor():
    """监控逻辑"""
    for ex_name in exchanges:
        ex = exchanges[ex_name]
        for symbol in symbols_config[ex_name]:
            try:
                # 初始化该交易对的历史记录
                if symbol not in history[ex_name]:
                    history[ex_name][symbol] = {
                        'funding_rate': None,
                        'open_interest': None,
                        'prices': [],
                        'last_alert_fr': None  # 新增：记录上次通知状态
                    }
                
                # 获取资金费率（仅监控永续合约）
                fr = ex.fetch_funding_rate(symbol)
                current_fr = fr['fundingRate']
                
                ################################################
                # 修改点1：仅当资金费率 < -1% 时触发警报
                ################################################
                if current_fr < -0.01:
                    # 避免重复通知（仅在首次低于阈值时发送）
                    if history[ex_name][symbol]['last_alert_fr'] is None or history[ex_name][symbol]['last_alert_fr'] >= -0.01:
                        msg = (
                            f"**资金费率异常**\n"
                            f">交易所：{ex_name}\n"
                            f">代币：{symbol}\n"
                            f">当前费率：{current_fr * 100:.4f}%\n"
                            f"⚠️ **费率低于 -1%**"
                        )
                        send_to_wx(msg)
                    history[ex_name][symbol]['last_alert_fr'] = current_fr
                else:
                    # 重置状态（如果费率回升到阈值以上）
                    history[ex_name][symbol]['last_alert_fr'] = None
                
                # 更新历史资金费率（保留原始逻辑）
                history[ex_name][symbol]['funding_rate'] = current_fr

                # 其余监控逻辑（持仓量、价格涨幅等，保持不变）
                # ...

            except ccxt.BaseError as e:
                print(f"API请求失败 {ex_name} {symbol}: {e}")
            except Exception as e:
                print(f"未知错误 {ex_name} {symbol}: {e}")

# 每5分钟运行一次监控
while True:
    monitor()
    time.sleep(300)