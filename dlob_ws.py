import asyncio
import os
import json
import time
import websockets
import signal
import traceback
import aiosqlite
from loguru import logger

PRICE_PRECISION = 1_000_000

class DlobClient:
    def __init__(self, url="wss://dlob.drift.trade/ws", db_path=".price_history.db"):
        self.url = url
        self.websocket = None
        self.is_connected = False   # the state of connection
        self.is_exited = False    # set to True when ctrl+c to stop reading messages
        self.last_heartbeat = time.time()
        self.reconnect_lock = asyncio.Lock()  # 一个锁，保证当网络突然断开时，reconnect函数不会被并发同时执行
        self.last_error_logger = None
        self.last_reconnect_logger = None
        self.subscribe_channel = []
        self.orderbooks = {}        # Store orderbooks for different markets

        self.db_path = db_path
        self.db_conn = None  # 由于aiosqlite的connect是异步的，不能在__init__中直接连接数据库

    async def connect_db(self):
        self.db_conn = await aiosqlite.connect(self.db_path)
        logger.info(f"Connected to DB at {self.db_path}")
        await self.db_conn.execute('CREATE TABLE IF NOT EXISTS price_history (symbol TEXT NOT NULL, price REAL NOT NULL, timestamp REAL NOT NULL)')
        await self.db_conn.commit()
        logger.info("DB initialized or already exists.")

    async def open_connection(self):
        try:
            logger.info("Opening dlob websocket connection...")
            self.websocket = await websockets.connect(self.url, ssl=True)
            if self.websocket.open:
                logger.info("Connected to the dlob server")
                self.is_connected = True
                await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Error thrown when opening connection: {e}")
            # logger.error(traceback.format_exc())
            await asyncio.sleep(5)

    async def close_connection(self):
        try:
            logger.info("Closing connection...")
            if self.websocket:
                await self.websocket.close()
                self.is_connected = False 
            logger.info("Connection closed")
        except Exception as e:
            logger.error(f"Error thrown when closing connection: {e}")
            logger.error(traceback.format_exc())

    async def reconnect(self, retries=5, delay=20):
        async with self.reconnect_lock:
            if self.is_connected and time.time() - self.last_heartbeat < 10:
                # 首次重连，或距离上一次日志报错20秒以上才在日志输出，防止刷屏
                if not self.last_reconnect_logger or time.time() - self.last_reconnect_logger > 20:
                    self.last_reconnect_logger = time.time()
                    logger.info("Already connected. No need to reconnect.")
                return
            logger.warning("Start to reconnect...")
            for attempt in range(retries):
                try:
                    await self.close_connection()
                    await self.open_connection()
                    if self.websocket.open:
                        for subscribe_channel in self.subscribe_channel:
                            if subscribe_channel['channel'] == 'orderbook':
                                await self.subscribe_orderbook(subscribe_channel['marketType'], subscribe_channel['market'])
                        logger.info("Successfully reconnected to Dlob websocket.")
                        return
                except Exception as e:
                    logger.error(f"Reconnect attempt {attempt + 1} failed: {e}")
                    # logger.error(traceback.format_exc())
                if attempt < retries - 1:
                    logger.warning(f"Wait {delay} seconds and try a new attempt...")
                    await asyncio.sleep(delay)
            logger.error("Failed to reconnect to Dlob websocket after multiple attempts.")

    async def subscribe_orderbook(self, marketType: str, market: str):
        if self.websocket and self.websocket.open:
            subscribe_channel = {'type': 'subscribe', 'marketType': marketType, 'channel': 'orderbook', 'market': market}
            if subscribe_channel not in self.subscribe_channel:
                self.subscribe_channel.append(subscribe_channel)
            logger.info(f"Subscribe to {market} orderbook...")
            await self.websocket.send(json.dumps(subscribe_channel))
            self.orderbooks[market] = {'bids': [], 'asks': []}  # Initialize orderbook for the market

    async def unsubscribe_orderbook(self, marketType: str, market: str):
        if self.websocket and self.websocket.open:
            logger.info(f"Unsubscribe to {market} orderbook...")
            await self.websocket.send(json.dumps({'type': 'unsubscribe', 'marketType': marketType, 'channel': 'orderbook', 'market': market}))
            subscribe_channel = {'type': 'subscribe', 'marketType': marketType, 'channel': 'orderbook', 'market': market}
            if subscribe_channel in self.subscribe_channel:
                self.subscribe_channel.remove(subscribe_channel)
            if market in self.orderbooks:
                del self.orderbooks[market]  # Remove orderbook for the market

    async def read_messages(self, read_timeout=0.5, backoff=0.5, on_disconnect=None):
        while not self.is_exited:
            try:
                if self.websocket and self.websocket.open:
                    message = await asyncio.wait_for(
                        self.websocket.recv(), timeout=read_timeout
                    )
                    message = json.loads(message)
                    if message.get('channel') == 'heartbeat':
                        self.last_heartbeat = time.time()
                        # logger.info("Heartbeat received")
                        # logger.info(self.last_heartbeat)
                    else:
                        yield message
                else:
                    if not self.is_exited:
                        raise Exception(f"The websocket connection is not opened.")
            except asyncio.TimeoutError:
                await asyncio.sleep(backoff)
            except Exception as e:
                if not self.is_exited:
                    # 首次报错，或距离上一次日志报错20秒以上才在日志输出，防止刷屏
                    # if not self.last_error_logger or time.time() - self.last_error_logger > 20:
                    #     self.last_error_logger = time.time()
                    logger.info("WebSocket connection closed")
                    logger.error(e)
                    # logger.error(traceback.format_exc())
                    await self.reconnect()
                    await asyncio.sleep(10)

    async def process_messages(self):
        async for message in self.read_messages():
            try:
                if 'data' in message and 'channel' in message:
                    channel_name = message['channel']
                    if 'orderbook' in channel_name:
                        # 根据消息中的channel_name确定是哪个资产的订单簿需要更新
                        prep_symbol = ''
                        if 'perp_0' in channel_name:
                            prep_symbol = 'SOL-PERP'
                        elif 'perp_1' in channel_name:
                            prep_symbol = 'BTC-PERP'
                        elif 'perp_2' in channel_name:
                            prep_symbol = 'ETH-PERP'

                        if prep_symbol:
                            data = json.loads(message['data'])
                            bids = [float(bid['price']) / PRICE_PRECISION for bid in data.get('bids', [])[:10]]
                            asks = [float(ask['price']) / PRICE_PRECISION for ask in data.get('asks', [])[:10]]
                            await self.update_orderbook(prep_symbol, bids, asks)
                elif 'message' in message:
                    logger.info(f"{message['message']}")
                else:
                    logger.warning(f"Received message: {message}")
            except Exception as e:
                logger.error(f"Error in processing message: {e}")

    async def update_orderbook(self, market, bids, asks):
        if market in self.orderbooks:
            self.orderbooks[market]['bids'] = bids
            self.orderbooks[market]['asks'] = asks
            if len(bids) > 0 and len(asks) > 0:
                current_price = (bids[0] + asks[0]) / 2
                timestamp = time.time()
                await self.db_conn.execute('INSERT INTO price_history (symbol, price, timestamp) VALUES (?, ?, ?)', (market, current_price, timestamp))
                await self.db_conn.commit()

    def get_orderbook(self, market):
        if market in self.orderbooks:
            return self.orderbooks.get(market, {'bids': [], 'asks': []})
        else:
            return {'bids': [], 'asks': []}

# Below is the example to use the DlobClient

async def manage_messages(dlob_client: DlobClient):
    async for message in dlob_client.read_messages():
        try:
            if 'data' in message and 'channel' in message:
                channel_name = message['channel']
                if 'orderbook' in channel_name:
                    if 'perp_0' in channel_name:  # for SOL-PERP
                        data = json.loads(message['data'])
                        bids = [float(bid['price']) / PRICE_PRECISION for bid in data.get('bids', [])[:10]]
                        asks = [float(ask['price']) / PRICE_PRECISION for ask in data.get('asks', [])[:10]]
                        # logger.info(f"Bids: {bids}")
                        # logger.info(f"Asks: {asks}")
            else:
                logger.info(f"Received message: {message}")
        except Exception as e:
            logger.error(f"Invalid message: {e}")

async def shutdown(dlob_client: DlobClient):
    try:
        logger.warning('SIGINT or CTRL-C detected. Initiating safe exit...')
        await dlob_client.unsubscribe_orderbook('perp', 'SOL-PERP')
        await dlob_client.close_connection()
        os._exit(0)
    except Exception as e:
        logger.error(f"Error when shutting down: {e}")

async def main():
    dlob_client = DlobClient()
    await dlob_client.open_connection()
    await dlob_client.subscribe_orderbook('perp', 'SOL-PERP')

    loop = asyncio.get_running_loop()
    for sig in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, sig), lambda: asyncio.create_task(shutdown(dlob_client)))

    reader_task = asyncio.create_task(await manage_messages(dlob_client))
    await reader_task  # make sure the reader_task is await to execute

if __name__ == "__main__":
    asyncio.run(main())

    
