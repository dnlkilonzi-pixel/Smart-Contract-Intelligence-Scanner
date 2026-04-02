"""
/api/v1/realtime — WebSocket endpoint for live threat alerts and scan progress.

Endpoints
---------
- ``/realtime/threats``         : live mempool threat feed (existing)
- ``/realtime/scan/{task_id}``  : real-time progress stream for a Celery scan task

Protocol (threats)
------------------
  - Server sends: JSON threat alert objects
  - Server sends: {"type": "ping"} heartbeat every 30 s

Protocol (scan progress)
------------------------
  - Server sends: {"type": "progress", "task_id": "…", "state": "…", "progress": N, "step": "…"}
  - Server sends: {"type": "result",   "task_id": "…", "result": {…}} on completion
  - Server sends: {"type": "error",    "task_id": "…", "error": "…"} on failure
  - Server sends: {"type": "ping"} heartbeat every 30 s
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


# ---------------------------------------------------------------------------
# Scan progress streaming
# ---------------------------------------------------------------------------

# Poll interval (seconds) when streaming Celery task progress
_POLL_INTERVAL_S = 1.0


@router.websocket("/scan/{task_id}")
async def scan_progress_ws(websocket: WebSocket, task_id: str) -> None:
    """
    WebSocket endpoint — streams real-time progress for a background scan task.

    Connect with: ws://host:8000/api/v1/realtime/scan/{task_id}

    The server polls the Celery result backend every second and pushes state
    updates until the task completes or fails.
    """
    await websocket.accept()
    log.info("scan_ws_client_connected", task_id=task_id)

    heartbeat_task = asyncio.create_task(_heartbeat(websocket))

    try:
        from celery.result import AsyncResult

        from app.worker import celery_app

        terminal_states = {"SUCCESS", "FAILURE", "REVOKED"}

        while True:
            try:
                result: AsyncResult = celery_app.AsyncResult(task_id)
                state = result.state
                meta = result.info or {}

                if state == "SUCCESS":
                    payload = {
                        "type": "result",
                        "task_id": task_id,
                        "state": state,
                        "result": meta if isinstance(meta, dict) else {},
                    }
                    await websocket.send_text(json.dumps(payload))
                    break

                if state in ("FAILURE", "REVOKED"):
                    payload = {
                        "type": "error",
                        "task_id": task_id,
                        "state": state,
                        "error": str(meta),
                    }
                    await websocket.send_text(json.dumps(payload))
                    break

                progress_meta = meta if isinstance(meta, dict) else {}
                payload = {
                    "type": "progress",
                    "task_id": task_id,
                    "state": state,
                    "progress": progress_meta.get("progress", 0),
                    "step": progress_meta.get("step", ""),
                }
                await websocket.send_text(json.dumps(payload))

            except WebSocketDisconnect:
                break
            except Exception as exc:
                log.warning("scan_ws_poll_error", task_id=task_id, error=str(exc))

            await asyncio.sleep(_POLL_INTERVAL_S)

    except WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        log.info("scan_ws_client_disconnected", task_id=task_id)
