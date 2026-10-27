#!/usr/bin/env python3
import asyncio
import json
import logging
import sys
import uuid
import threading
from typing import Any, Dict, List

import websockets

LOG_FILE = "/home/kenerth/IA redes/mcp_server.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

bridge_ws = None
pending_requests: Dict[str, asyncio.Future] = {}

async def handle_bridge_messages():
    global bridge_ws
    while True:
        try:
            if bridge_ws is None:
                await asyncio.sleep(1)
                continue
            message = await bridge_ws.recv()
            data = json.loads(message)
            request_id = data.get('id')
            if request_id and request_id in pending_requests:
                f = pending_requests.pop(request_id)
                if not f.done():
                    f.set_result(data)
        except:
            bridge_ws = None
            await asyncio.sleep(2)

async def send_to_bridge(action: str, params=None):
    global bridge_ws
    if params is None:
        params = {}
    if bridge_ws is None:
        raise Exception("Bridge no conectado")
    request_id = str(uuid.uuid4())
    req = {"id": request_id, "action": action, "params": params}
    fut = asyncio.get_event_loop().create_future()
    pending_requests[request_id] = fut
    await bridge_ws.send(json.dumps(req))
    return await asyncio.wait_for(fut, timeout=8.0)

async def ws_handler(websocket):
    global bridge_ws
    logger.info("Bridge conectado")
    bridge_ws = websocket
    try:
        await websocket.wait_closed()
    finally:
        if bridge_ws == websocket:
            bridge_ws = None
        logger.info("Bridge desconectado")

def _run_ws():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def start():
        ws = await websockets.serve(ws_handler, "127.0.0.1", 8765)
        logger.info("WS en ws://127.0.0.1:8765")
        asyncio.create_task(handle_bridge_messages())
        await ws.wait_closed()
    loop.run_until_complete(start())

if __name__ == "__main__":
    t = threading.Thread(target=_run_ws, daemon=True)
    t.start()
    logger.info("Servidor listo")
    # mantener vivo
    try:
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        pass
