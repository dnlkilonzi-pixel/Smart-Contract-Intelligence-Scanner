"""
/api/v1/realtime — WebSocket endpoint for live threat alerts.

Clients connect via WebSocket and receive a stream of threat alert JSON
messages whenever the mempool listener detects a new high-risk contract.

Protocol:
  - Server sends: JSON threat alert objects (see mempool_listener._build_alert)
  - Server sends: {"type": "ping"} heartbeat every 30 s
  - Client may send: any text (ignored; kept alive)
"""
from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.intelligence.mempool_listener import alert_queue

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/realtime", tags=["realtime"])

# Reconnection delay constant (ms) for client-side documentation purposes
HEARTBEAT_INTERVAL_S = 30

# In-memory set of all connected WebSocket clients
_clients: set[WebSocket] = set()


@router.websocket("/threats")
async def threats_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint — streams live threat alerts to the client.

    Connect with: ws://host:8000/api/v1/realtime/threats
    """
    await websocket.accept()
    _clients.add(websocket)
    log.info("ws_client_connected", total=len(_clients))

    # Each client gets its own queue populated by the fan-out task.
    client_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    _fan_out_registry[id(websocket)] = client_queue

    heartbeat_task = asyncio.create_task(_heartbeat(websocket))
    # Background task: copy new alerts from the shared queue to this client queue
    drain_task = asyncio.create_task(_drain_shared_queue(client_queue))

    try:
        while True:
            # Wait for the next alert with a 1-second timeout so we can also
            # detect a disconnected client promptly.
            try:
                alert = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                await websocket.send_text(json.dumps(alert))
            except asyncio.TimeoutError:
                # No alerts yet — check if the client is still alive via a
                # non-blocking receive attempt.
                try:
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        drain_task.cancel()
        _fan_out_registry.pop(id(websocket), None)
        _clients.discard(websocket)
        log.info("ws_client_disconnected", total=len(_clients))


# Registry mapping websocket id → per-client queue for fan-out
_fan_out_registry: dict[int, asyncio.Queue] = {}


async def _drain_shared_queue(client_queue: asyncio.Queue) -> None:
    """Continuously move alerts from the shared queue into a per-client queue."""
    try:
        while True:
            alert = await alert_queue.get()
            # Fan-out: also put into all other client queues
            for q in list(_fan_out_registry.values()):
                if not q.full():
                    try:
                        q.put_nowait(alert)
                    except asyncio.QueueFull:
                        pass
    except asyncio.CancelledError:
        pass


async def broadcast_alert(alert: dict) -> None:
    """Broadcast *alert* to all connected WebSocket clients directly."""
    dead: list[WebSocket] = []
    for ws in list(_clients):
        try:
            await ws.send_text(json.dumps(alert))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


async def _heartbeat(websocket: WebSocket) -> None:
    """Send a ping frame every HEARTBEAT_INTERVAL_S seconds to keep the connection alive."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except Exception:
        pass
