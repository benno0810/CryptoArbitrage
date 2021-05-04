import json
import threading
import time

import asyncio
import websockets

import logging
logger = logging.getLogger('websockets')
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


class A(threading.Thread):
    def __init__(self):
        super().__init__()
        self.websocket = None
        self.base_url = 'wss://api.bitfinex.com/ws/2'
        self.loop = asyncio.new_event_loop()

    async def init(self):
        print('init conn')
        self.websocket = await websockets.connect(self.base_url)

    async def _connect(self):
        while True:
            print('conn')
            self.websocket = await websockets.connect(self.base_url)
            await asyncio.sleep(5)
            print('disconn')
            await self.websocket.close()
            print(self.websocket.open)
            await asyncio.sleep(5)

    async def ws_handler(self):
        '''
        handle task in backthread
        :return:
        '''
        while True:
            channel = None
            try:
                data = await asyncio.wait_for(self.websocket.recv(), timeout=20)
            except Exception as ex:
                try:
                    logging.error('Bitfinex ws_handler: %s' % ex)
                    # await asyncio.sleep(5)
                    pong_waiter = await self.websocket.ping()
                    await asyncio.wait_for(pong_waiter, timeout=10)
                except asyncio.TimeoutError:
                    # No response to ping in 10 seconds, disconnect.
                    self.depth = {}
                    break
                except Exception:
                    self.depth = {}
                    break
            else:
                print(json.loads(data))

    async def send(self):
        while True:
            pong_waiter = await self.websocket.ping()
            await asyncio.wait_for(pong_waiter, timeout=10)

    def run(self):
        while True:
            try:
                self.loop.run_until_complete(self.init())
                # self.loop.run_until_complete(self.ws_init())
                tasks = [self.ws_handler(), self.send(), self._connect()]
                self.loop.run_until_complete(asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED))
                time.sleep(1)
            except Exception as ex:
                logging.error(ex)

def test_to():
    start = time.time()
    while True:
        time.sleep(0.01)
        if time.time() - 5 > start:
            print("timeout")
            raise TimeoutError
try:
    test_to()
except Exception as ex:
    logging.error('timeout')