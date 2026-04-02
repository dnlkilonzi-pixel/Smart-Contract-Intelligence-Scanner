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

    # Drain queue for this client by polling
    ping_task = asyncio.create_task(_heartbeat(websocket))

    try:
        while True:
            # Poll the shared queue with a short timeout so we can also
            # detect client disconnects via the receive side.
            try:
                alert = alert_queue.get_nowait()
                await websocket.send_text(json.dumps(alert))
            except asyncio.QueueEmpty:
                # Nothing to send; check if client is still alive
                try:
                    # Non-blocking receive attempt
                    await asyncio.wait_for(websocket.receive_text(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
                except WebSocketDisconnect:
                    break
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        pass
    finally:
        ping_task.cancel()
        _clients.discard(websocket)
        log.info("ws_client_disconnected", total=len(_clients))


async def broadcast_alert(alert: dict) -> None:
    """
    Broadcast *alert* to all connected WebSocket clients.

    Called by the mempool listener (fire-and-forget fan-out).
    """
    dead: list[WebSocket] = []
    for ws in list(_clients):
        try:
            await ws.send_text(json.dumps(alert))
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.discard(ws)


async def _heartbeat(websocket: WebSocket) -> None:
    """Send a ping frame every 30 s to keep the connection alive."""
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except Exception:
        pass
