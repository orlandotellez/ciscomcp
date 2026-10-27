#!/usr/bin/env python3
import asyncio
import errno
import json
import logging
import os
import sys
import threading
import uuid
from typing import Any, Dict, List, Optional

import websockets
from mcp.server.fastmcp import FastMCP

BASE_DIR = "/home/kenerth/IA redes"
LOG_FILE = os.path.join(BASE_DIR, "mcp_server.log")
WS_HOST = "127.0.0.1"
WS_PORT = 8765
WS_URL = f"ws://{WS_HOST}:{WS_PORT}"

# Configurar logger sin duplicar handlers
logger = logging.getLogger("packettracer_mcp")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    fmt = logging.Formatter("%(asctime)s [PID:%(process)d] - %(levelname)s - %(message)s")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(sh)

mcp = FastMCP("packettracer")

# Estado del Hub WebSocket (en el proceso que sea dueño del puerto 8765)
hub_bridge_ws: Optional[Any] = None
hub_pending: Dict[str, asyncio.Future] = {}
hub_loop: Optional[asyncio.AbstractEventLoop] = None
is_hub_owner: bool = False


async def _hub_send_to_pt(action: str, params: Dict[str, Any], timeout: float = 10.0) -> Dict[str, Any]:
    global hub_bridge_ws
    if hub_bridge_ws is None:
        raise RuntimeError(
            "El Bridge de Packet Tracer NO está conectado a ws://127.0.0.1:8765. "
            "En Packet Tracer ve a Extensions -> Scripting -> Configure PT Script Modules -> Edit -> Start."
        )
    rid = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    hub_pending[rid] = fut
    payload = {"id": rid, "action": action, "params": params}
    logger.info(f"[HUB -> PT] Enviando acción '{action}' (id={rid}) params={params}")
    try:
        await hub_bridge_ws.send(json.dumps(payload))
        result = await asyncio.wait_for(fut, timeout=timeout)
        logger.info(f"[PT -> HUB] Respuesta recibida para '{action}' (id={rid}): success={result.get('success')}")
        return result
    except asyncio.TimeoutError:
        hub_pending.pop(rid, None)
        logger.error(f"[HUB] Timeout esperando respuesta de Packet Tracer para '{action}' (id={rid})")
        raise RuntimeError(f"Timeout ({timeout}s) esperando respuesta del Bridge en Packet Tracer para '{action}'")
    except Exception as e:
        hub_pending.pop(rid, None)
        logger.error(f"[HUB] Error enviando '{action}' a Packet Tracer: {e}")
        raise


async def _hub_ws_handler(ws: Any):
    """
    Maneja tanto:
    1) La conexión del WebView Bridge de Packet Tracer (bridge.html)
    2) Peticiones proxy de otros procesos server.py (mcp_proxy_request)
    """
    global hub_bridge_ws
    peer = getattr(ws, "remote_address", ("?", "?"))
    logger.info(f"[HUB] Nueva conexión WebSocket entrante desde {peer}")

    # Por defecto, si aún no hay bridge conectado, asumimos que puede ser el bridge
    registered_as_proxy = False
    if hub_bridge_ws is None:
        hub_bridge_ws = ws
        logger.info(f"[HUB] Bridge de Packet Tracer asignado inicialmente ({peer})")

    try:
        async for raw_msg in ws:
            try:
                data = json.loads(raw_msg)
            except Exception as e:
                logger.warning(f"[HUB] Mensaje no-JSON recibido: {raw_msg!r} ({e})")
                continue

            msg_type = data.get("type")

            # 1) Identificación explícita del Bridge de Packet Tracer
            if msg_type == "register_bridge":
                hub_bridge_ws = ws
                logger.info(f"[HUB] Bridge de Packet Tracer conectado y registrado ({data.get('client')})")
                await ws.send(json.dumps({"type": "welcome", "status": "connected"}))
                continue

            # 2) Logs enviados desde bridge.html hacia mcp_server.log
            if msg_type == "bridge_log":
                lvl = str(data.get("level", "info")).upper()
                msg = data.get("message", "")
                logger.info(f"[PT-BRIDGE-LOG] [{lvl}] {msg}")
                continue

            # 3) Consulta de estado del Hub
            if msg_type == "hub_status":
                registered_as_proxy = True
                if hub_bridge_ws == ws:
                    hub_bridge_ws = None
                await ws.send(json.dumps({
                    "type": "hub_status_response",
                    "bridge_connected": hub_bridge_ws is not None,
                    "hub_pid": os.getpid()
                }))
                continue

            # 4) Petición desde un proceso MCP secundario (proxy) hacia Packet Tracer
            if msg_type == "mcp_proxy_request":
                registered_as_proxy = True
                if hub_bridge_ws == ws:
                    hub_bridge_ws = None
                req_id = data.get("id")
                action = data.get("action")
                params = data.get("params") or {}
                try:
                    res = await _hub_send_to_pt(action, params)
                    await ws.send(json.dumps({"id": req_id, "proxy_ok": True, "result": res}))
                except Exception as e:
                    await ws.send(json.dumps({"id": req_id, "proxy_ok": False, "error": str(e)}))
                continue

            # 5) Respuesta normal de Packet Tracer a un comando enviado por el Hub
            rid = data.get("id")
            if rid and rid in hub_pending:
                fut = hub_pending.pop(rid)
                if not fut.done():
                    fut.set_result(data)
            else:
                logger.info(f"[PT -> HUB] Mensaje recibido de PT: {data}")

    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"[HUB] Conexión WebSocket cerrada ({peer}): code={e.code}")
    except Exception as e:
        logger.error(f"[HUB] Error en conexión WebSocket ({peer}): {e}")
    finally:
        if hub_bridge_ws == ws:
            hub_bridge_ws = None
            logger.warning("[HUB] Bridge de Packet Tracer desconectado.")
        elif not registered_as_proxy:
            logger.info(f"[HUB] Cliente desconectado ({peer}).")


def _start_hub_thread():
    global hub_loop, is_hub_owner
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    hub_loop = loop

    async def _run_server():
        global is_hub_owner
        try:
            srv = await websockets.serve(_hub_ws_handler, WS_HOST, WS_PORT)
            is_hub_owner = True
            logger.info(f"[HUB] Servidor WebSocket escuchando en {WS_URL}")
            await srv.wait_closed()
        except OSError as e:
            if e.errno == errno.EADDRINUSE:
                is_hub_owner = False
                logger.info(
                    f"[PROXY] El puerto {WS_PORT} ya está en uso por otro proceso MCP. "
                    f"Este proceso (PID {os.getpid()}) operará en modo cliente proxy hacia {WS_URL}."
                )
            else:
                logger.error(f"[HUB] Error de red al iniciar WebSocket en {WS_URL}: {e}")
        except Exception as e:
            logger.error(f"[HUB] Error inesperado en servidor WebSocket: {e}")

    loop.run_until_complete(_run_server())


async def send(action: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Envía una acción al Bridge de Packet Tracer.
    - Si este proceso es dueño del Hub (puerto 8765), despacha directamente en el event loop del Hub.
    - Si otro proceso server.py tiene el puerto 8765, se conecta como cliente proxy a ws://127.0.0.1:8765.
    """
    if params is None:
        params = {}

    if is_hub_owner and hub_loop is not None:
        cfut = asyncio.run_coroutine_threadsafe(_hub_send_to_pt(action, params), hub_loop)
        return await asyncio.wrap_future(cfut)

    # Modo proxy cliente hacia el proceso que posee ws://127.0.0.1:8765
    req_id = str(uuid.uuid4())
    logger.info(f"[PROXY -> HUB] Enviando '{action}' (id={req_id}) vía {WS_URL}")
    async with websockets.connect(WS_URL, open_timeout=5) as ws:
        await ws.send(json.dumps({
            "type": "mcp_proxy_request",
            "id": req_id,
            "action": action,
            "params": params
        }))
        raw = await asyncio.wait_for(ws.recv(), timeout=12.0)
        resp = json.loads(raw)
        if not resp.get("proxy_ok"):
            raise RuntimeError(resp.get("error", "Error desconocido en Hub MCP"))
        return resp["result"]


@mcp.tool()
async def ping_bridge() -> Dict[str, Any]:
    """Verifica si el Bridge de Packet Tracer está conectado y responde a llamadas IPC."""
    return await send("ping")


@mcp.tool()
async def get_bridge_logs(lines: int = 60) -> Dict[str, Any]:
    """Devuelve el estado de conexión del Bridge y las últimas líneas de mcp_server.log."""
    bridge_connected = False
    hub_pid = None
    if is_hub_owner:
        bridge_connected = hub_bridge_ws is not None
        hub_pid = os.getpid()
    else:
        try:
            async with websockets.connect(WS_URL, open_timeout=3) as ws:
                await ws.send(json.dumps({"type": "hub_status"}))
                st = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
                bridge_connected = st.get("bridge_connected", False)
                hub_pid = st.get("hub_pid")
        except Exception:
            pass

    log_tail: List[str] = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
            log_tail = [ln.rstrip("\n") for ln in all_lines[-max(1, lines):]]

    return {
        "bridge_connected": bridge_connected,
        "hub_pid": hub_pid,
        "current_pid": os.getpid(),
        "log_file": LOG_FILE,
        "recent_logs": log_tail,
    }


@mcp.tool()
async def list_devices() -> Dict[str, Any]:
    """Lista todos los dispositivos en la topología actual de Packet Tracer."""
    return await send("list_devices")


@mcp.tool()
async def add_device(device_type: str, model: str, name: str, x: int = 100, y: int = 100) -> Dict[str, Any]:
    """Añade un dispositivo a Packet Tracer (ej. device_type='router'|'switch'|'pc', model='2911'|'2960-24TT'|'PC-PT')."""
    return await send("add_device", {
        "device_type": device_type,
        "model": model,
        "name": name,
        "x": x,
        "y": y
    })


@mcp.tool()
async def remove_device(name: str) -> Dict[str, Any]:
    """Elimina un dispositivo por nombre de la topología de Packet Tracer."""
    return await send("remove_device", {"name": name})


@mcp.tool()
async def get_device_ports(device: str) -> Dict[str, Any]:
    """Obtiene la lista de puertos e IPs de un dispositivo en Packet Tracer."""
    return await send("get_device_ports", {"device": device})


@mcp.tool()
async def connect_link(dev1: str, port1: str, dev2: str, port2: str, cable_type: str = "straight") -> Dict[str, Any]:
    """Conecta dos dispositivos con un cable (straight, cross, fiber, serial, console, auto)."""
    return await send("connect_link", {
        "dev1": dev1,
        "port1": port1,
        "dev2": dev2,
        "port2": port2,
        "cable_type": cable_type
    })


@mcp.tool()
async def configure_ios(device: str, commands: List[str]) -> Dict[str, Any]:
    """Ejecuta una lista de comandos IOS CLI en un router o switch de Packet Tracer."""
    return await send("configure_ios", {"device": device, "commands": commands})


@mcp.tool()
async def configure_pc_ip(
    device: str,
    ip: str,
    subnet_mask: str = "255.255.255.0",
    gateway: str = "0.0.0.0",
    dhcp: bool = False
) -> Dict[str, Any]:
    """Configura la dirección IP, máscara, gateway o DHCP en una PC/Server de Packet Tracer."""
    return await send("configure_pc_ip", {
        "device": device,
        "ip": ip,
        "subnet_mask": subnet_mask,
        "gateway": gateway,
        "dhcp": dhcp
    })


if __name__ == "__main__":
    if "--hub" in sys.argv:
        logger.info("[HUB-STANDALONE] Iniciando Hub WebSocket dedicado en ws://127.0.0.1:8765...")
        _start_hub_thread()
        sys.exit(0)

    t = threading.Thread(target=_start_hub_thread, daemon=True)
    t.start()
    try:
        mcp.run()
    except Exception as e:
        logger.error(f"Error fatal en mcp.run(): {e}")
        sys.exit(1)
