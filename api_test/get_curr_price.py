import requests

def get_curr_price(symbol):
    url = f"http://localhost:8080/price/{symbol}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching current price for {symbol}: {response.status_code}")
        return None

# 获取BTC-PERP的当前价格数据
curr_price = get_curr_price("BTC-PERP")
if curr_price:
    print(curr_price)
