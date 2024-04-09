from dlob_client import DlobLocalClient

dlob_local_cilent = DlobLocalClient()

price_history = dlob_local_cilent.get_price_history(symbol="BTC-PERP", interval=60, limit=20)

print(price_history)