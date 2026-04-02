"""
Celery worker — async task queue for long-running smart contract scans.

Tasks
-----
- ``scan_contract_task``  : run the full scanning pipeline in the background
- ``scan_address_task``   : fetch + scan a deployed contract by on-chain address

Usage (CLI)
-----------
Start a worker process (from the project root):

    celery -A app.worker worker --loglevel=info --concurrency=2

Schedule a scan from application code:

    from app.worker import scan_contract_task
    result = scan_contract_task.delay(source_code="pragma solidity …")
    task_id = result.id           # store and poll for progress

Check task status via the REST API:

    GET /api/v1/scanner/task/{task_id}
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

import structlog
from celery import Celery
from celery.signals import after_setup_logger, worker_init, worker_shutdown
from celery.utils.log import get_task_logger

from app.config import get_settings

settings = get_settings()

log = structlog.get_logger(__name__)
task_log = get_task_logger(__name__)

# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

celery_app = Celery(
    "smart_contract_scanner",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task behaviour
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Result expiry — keep results for 24 hours
    result_expires=86400,
    # Retry policy — retry up to 3 times with exponential back-off
    task_max_retries=3,
    task_default_retry_delay=30,
    # Routing
    task_routes={
        "app.worker.scan_contract_task": {"queue": "scans"},
        "app.worker.scan_address_task": {"queue": "scans"},
    },
)


# ---------------------------------------------------------------------------
# Signal handlers — manage the asyncio event loop for the worker process
# ---------------------------------------------------------------------------

_loop: Optional[asyncio.AbstractEventLoop] = None


@worker_init.connect
def _init_loop(**_kwargs: Any) -> None:
    global _loop
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)


@worker_shutdown.connect
def _close_loop(**_kwargs: Any) -> None:
    if _loop and not _loop.is_closed():
        _loop.close()


@after_setup_logger.connect
def _configure_logging(logger: logging.Logger, **_kwargs: Any) -> None:
    """Integrate Celery's logger with structlog."""
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Helper — run an async coroutine from a synchronous Celery task
# ---------------------------------------------------------------------------

def _run_async(coro: Any) -> Any:
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

@celery_app.task(
    name="app.worker.scan_contract_task",
    bind=True,
    max_retries=3,
)
def scan_contract_task(
    self: Any,
    source_code: str,
    address: Optional[str] = None,
    compiler_version: str = "0.8.19",
    enable_mythril: bool = False,
) -> Dict[str, Any]:
    """
    Scan a Solidity contract source for vulnerabilities.

    Parameters
    ----------
    source_code:
        Raw Solidity source text.
    address:
        Optional deployed address to associate with the result.
    compiler_version:
        Solidity compiler version string.
    enable_mythril:
        Whether to run Mythril in addition to Slither.

    Returns
    -------
    dict
        Serialised ``ScanResponse`` from the scanning pipeline.
    """
    task_log.info("scan_contract_task started", task_id=self.request.id, address=address)
    self.update_state(state="STARTED", meta={"progress": 0, "step": "initialising"})

    async def _run() -> Dict[str, Any]:
        from app.models.database import AsyncSessionLocal
        from app.services.scan_service import ScanService

        async with AsyncSessionLocal() as db:
            service = ScanService(db)
            self.update_state(
                state="PROGRESS",
                meta={"progress": 10, "step": "running_static_analysis"},
            )
            result = await service.scan(
                source_code=source_code,
                address=address,
                compiler_version=compiler_version,
                enable_mythril=enable_mythril,
            )
            self.update_state(
                state="PROGRESS",
                meta={"progress": 90, "step": "persisting_results"},
            )
            return result.model_dump()

    try:
        return _run_async(_run())
    except Exception as exc:
        task_log.error("scan_contract_task failed", error=str(exc))
        raise self.retry(exc=exc, countdown=30) from exc


@celery_app.task(
    name="app.worker.scan_address_task",
    bind=True,
    max_retries=3,
)
def scan_address_task(
    self: Any,
    address: str,
    compiler_version: str = "0.8.19",
    enable_mythril: bool = False,
) -> Dict[str, Any]:
    """
    Fetch verified source from Etherscan for *address* and scan it.

    Parameters
    ----------
    address:
        Deployed contract address (0x…).
    compiler_version:
        Solidity compiler version to use.
    enable_mythril:
        Whether to also run Mythril.

    Returns
    -------
    dict
        Serialised ``ScanResponse`` from the scanning pipeline.
    """
    task_log.info("scan_address_task started", task_id=self.request.id, address=address)
    self.update_state(state="STARTED", meta={"progress": 0, "step": "fetching_source"})

    async def _run() -> Dict[str, Any]:
        from app.models.database import AsyncSessionLocal
        from app.services.scan_service import ScanService

        async with AsyncSessionLocal() as db:
            service = ScanService(db)
            self.update_state(
                state="PROGRESS",
                meta={"progress": 20, "step": "running_static_analysis"},
            )
            result = await service.scan(
                source_code=None,
                address=address,
                compiler_version=compiler_version,
                enable_mythril=enable_mythril,
            )
            self.update_state(
                state="PROGRESS",
                meta={"progress": 90, "step": "persisting_results"},
            )
            return result.model_dump()

    try:
        return _run_async(_run())
    except Exception as exc:
        task_log.error("scan_address_task failed", error=str(exc))
        raise self.retry(exc=exc, countdown=30) from exc
