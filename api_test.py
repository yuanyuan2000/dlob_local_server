from dlob_client import DlobLocalClient
import numpy as np

dlob_local_cilent = DlobLocalClient()
prep_symbol = "SOL-PERP"

orderbook = dlob_local_cilent.get_orderbook(prep_symbol)
if len(orderbook['bids']) and len(orderbook['asks']):
    bids = orderbook['bids']
    asks = orderbook['asks']
    print(f'Bids: {bids}')
    print(f'Asks: {asks}')
else:
    raise ValueError(f'Orderbook is not available')

prices = []
interval = 60
limit = 20
price_data_list = dlob_local_cilent.get_price_history(prep_symbol, interval, limit)
if 'prices' in price_data_list and len(price_data_list['prices']) == limit:
    # 有空白数据时取其之后最接近的数据补上
    empty_point = 0
    for price_data in price_data_list['prices']:
        if price_data is None:
            empty_point += 1
            continue
        else:
            for i in range(0, empty_point+1):
                prices.append(price_data)
            empty_point = 0
    if len(prices) == 0:
        raise ValueError(f'The format of historical price data is wrong')
    print(f'Historical price: {prices}')

    if len(prices) >= 20:
        price_list = np.array(prices[-20:])  # 转换为NumPy数组
    print(f'MA: {price_list.mean()}')
    print(f'Std: {price_list.std()}')
else:
    raise ValueError(f'The format of historical price data is wrong')