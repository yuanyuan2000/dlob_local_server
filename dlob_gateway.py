import asyncio
import json
import time
import os
import signal
from aiohttp import web
from dlob_ws import DlobClient

dlob_client = None
task_process_message = None

# 初始化DlobClient实例并连接到WebSocket
async def init_dlob_client(app):
    global dlob_client  # 使用全局变量
    dlob_client = DlobClient()
    await dlob_client.connect_db()  # 连接数据库
    await dlob_client.open_connection()
    # 订阅'SOL-PERP', 'BTC-PERP', 'ETH-PERP'
    for symbol in ['SOL-PERP', 'BTC-PERP', 'ETH-PERP']:
        await dlob_client.subscribe_orderbook('perp', symbol)
    app['dlob_client'] = dlob_client  # 保存到app中

# 定义请求处理函数
async def handle_request(request):
    symbol = request.match_info.get('symbol', "SOL-PERP")
    orderbook = request.app['dlob_client'].get_orderbook(symbol)  # 使用request.app访问全局app变量
    if orderbook['bids'] and orderbook['asks']:
        return web.json_response(orderbook)
    else:
        return web.json_response({'error': 'No data for the requested symbol'}, status=404)
    
async def handle_current_price(request):
    symbol = request.match_info.get('symbol', "SOL-PERP")
    async with request.app['dlob_client'].db_conn.execute('SELECT price FROM price_history WHERE symbol = ? ORDER BY timestamp DESC LIMIT 1', (symbol,)) as cursor:
        row = await cursor.fetchone()
    if row:
        return web.json_response({'current_price': row[0]})
    else:
        return web.json_response({'error': 'No data for the requested symbol'}, status=404)

async def handle_price_history(request):
    symbol = request.match_info.get('symbol', "SOL-PERP")
    interval = min(int(request.match_info.get('interval', 60)), 1800)  # 限制interval最大为1800秒
    limit = min(int(request.match_info.get('limit', 20)), 50)  # 限制最大值为50
    
    # 计算查询的起始时间点，稍微多获取一些数据以确保覆盖所需的时间段
    now = time.time()
    start_time = now - interval * (limit + 1)

    # 修改数据库查询，只获取timestamp大于计算出的start_time的数据
    async with request.app['dlob_client'].db_conn.execute(
        'SELECT price, timestamp FROM price_history WHERE symbol = ? AND timestamp > ? ORDER BY timestamp DESC', 
        (symbol, start_time)
    ) as cursor:
        prices = await cursor.fetchall()

    result = []
    timestamps_needed = [int(now - i * interval) for i in range(limit + 1)]
    # print(f'timestamps_needed = {timestamps_needed}')

    # 初始化用于追踪上一个找到的合适价格的变量
    last_found_index = 0
    # for needed_ts in reversed(timestamps_needed):
    for needed_ts in timestamps_needed:
        found_price = None
        # print(f'Current need ts is {needed_ts}:')
        # 从最新的价格开始，向后查找直到找到第一个符合当前时间间隔的价格
        for price, ts in prices[last_found_index:]:
            if ts <= needed_ts:
                # print(f'Founded price {price} at {int(ts)} is closer to the {needed_ts}')
                found_price = price
                last_found_index = prices.index((price, ts))  # 更新索引，下次搜索从这里开始
                break
        result.insert(0, found_price)  # 将找到的价格插入到结果列表的前端

    # 由于最开始添加了一个额外的时间点以确保覆盖，现在移除它对应的价格
    if len(result) > limit:
        result = result[1:]

    return web.json_response({'prices': result})


# 运行服务器
async def run_server(app):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

    global task_process_message  # 使用全局变量
    task_process_message = asyncio.create_task(dlob_client.process_messages())  # 启动消息处理任务

    loop = asyncio.get_running_loop()
    for sig in ('SIGINT', 'SIGTERM'):
        loop.add_signal_handler(getattr(signal, sig), lambda: asyncio.create_task(shutdown()))

    await task_process_message

async def shutdown():
    global task_process_message, dlob_client  # 使用全局变量
    print('SIGINT or CTRL-C detected. Initiating safe exit...')
    for symbol in ["SOL-PERP", "BTC-PERP", "ETH-PERP"]:
        await dlob_client.unsubscribe_orderbook('perp', symbol)
    await dlob_client.close_connection()
    dlob_client.is_exited = True
    await dlob_client.db_conn.close()  # 关闭与数据库的连接
    task_process_message.cancel()
    os._exit(0)

# 创建并配置aiohttp应用
app = web.Application()

# 添加处理订单簿请求的路由
app.router.add_get('/orderbook/{symbol}', handle_request)

# 添加处理当前价格请求的路由
app.router.add_get('/price/{symbol}', handle_current_price)

# 添加处理价格历史请求的路由
app.router.add_get('/price/{symbol}/{interval}/{limit}', handle_price_history)

# 确保初始化DlobClient实例并连接到WebSocket和数据库
app.on_startup.append(lambda app: init_dlob_client(app))

# 运行服务器
if __name__ == '__main__':
    asyncio.run(run_server(app))
