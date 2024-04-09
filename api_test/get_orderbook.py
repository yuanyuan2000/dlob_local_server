import requests

def get_orderbook(symbol):
    url = f"http://localhost:8080/orderbook/{symbol}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching orderbook for {symbol}: {response.status_code}")
        return None

# 获取SOL-PERP的订单簿数据
orderbook = get_orderbook("SOL-PERP")
if orderbook:
    print(orderbook)
