import requests

def get_price_history(symbol, interval=60, limit=20):
    # 构造请求URL
    url = f"http://localhost:8080/price/{symbol}/{interval}/{limit}"
    # 发送GET请求
    response = requests.get(url)
    # 检查响应状态码
    if response.status_code == 200:
        # 请求成功，返回JSON解析后的响应体
        return response.json()
    else:
        # 请求失败，打印错误信息
        print(f"Error fetching price history for {symbol}: {response.status_code}")
        return None

# 获取ETH-PERP的历史价格数据
price_history = get_price_history("ETH-PERP", interval=300)
if price_history:
    print(price_history)
