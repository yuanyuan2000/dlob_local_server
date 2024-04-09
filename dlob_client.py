import requests

CONFIG = {
    'rest_url': 'http://localhost:8080',
}

class DlobLocalClient():
    def __init__(self):
        self.client = requests

    def get_orderbook(self, symbol):
        url = f"{CONFIG['rest_url']}/orderbook/{symbol}"
        response = self.client.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching orderbook for {symbol}: {response.status_code}")
            return None
        
    def get_curr_price(self, symbol):
        url = f"{CONFIG['rest_url']}/price/{symbol}"
        response = self.client.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching current price for {symbol}: {response.status_code}")
            return None

    def get_price_history(self, symbol, interval=60, limit=20):
        url = f"{CONFIG['rest_url']}/price/{symbol}/{interval}/{limit}"
        response = self.client.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching price history for {symbol}: {response.status_code}")
            return None
        
    