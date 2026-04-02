"""
/api/v1/scanner — contract scanning endpoints.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schemas.contract import ScanRequest, ScanResponse
from app.services.report_service import generate_html_report, generate_json_report
from app.services.scan_service import ScanService

router = APIRouter(prefix="/scanner", tags=["scanner"])


# ---------------------------------------------------------------------------
# Async task submission schemas
# ---------------------------------------------------------------------------


class AsyncScanRequest(ScanRequest):
    """Identical to ScanRequest — submitted to the Celery queue instead."""


class AsyncScanResponse(BaseModel):
    """Returned when a scan is dispatched to the background task queue."""

    task_id: str
    status: str = "queued"
    status_url: str


class TaskStatusResponse(BaseModel):
    """Current state of a background scan task."""

    task_id: str
    state: str
    progress: Optional[int] = None
    step: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None


@router.post(
    "/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    summary="Scan a smart contract for vulnerabilities",
)
async def scan_contract(
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
) -> ScanResponse:
    """
    Submit a Solidity contract for full security analysis.

    - Provide **source_code** (raw Solidity) and/or a deployed **address**.
    - If only an address is given, verified source is fetched from Etherscan.
    - Set **enable_mythril=true** for deeper (but slower) symbolic execution.
    """
    if not body.source_code and not body.address:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one of: source_code, address",
        )

    service = ScanService(db)
    try:
        result = await service.scan(
            source_code=body.source_code,
            address=body.address,
            compiler_version=body.compiler_version or "0.8.19",
            enable_mythril=body.enable_mythril,
            chain=body.chain,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan failed: {exc}",
        ) from exc

    return result


# ---------------------------------------------------------------------------
# Async background scan (Celery)
# ---------------------------------------------------------------------------


@router.post(
    "/scan/async",
    response_model=AsyncScanResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a contract scan to the background task queue",
)
async def scan_contract_async(body: AsyncScanRequest) -> AsyncScanResponse:
    """
    Dispatch a contract scan to the Celery worker queue.

    Returns a ``task_id`` that you can poll via ``GET /scanner/task/{task_id}``.
    Connect to ``ws://host/api/v1/realtime/scan/{task_id}`` for real-time
    progress updates.
    """
    if not body.source_code and not body.address:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one of: source_code, address",
        )

    try:
        from app.worker import scan_address_task, scan_contract_task

        if body.source_code:
            result = scan_contract_task.delay(
                source_code=body.source_code,
                address=body.address,
                compiler_version=body.compiler_version or "0.8.19",
                enable_mythril=body.enable_mythril,
            )
        else:
            result = scan_address_task.delay(
                address=body.address,
                compiler_version=body.compiler_version or "0.8.19",
                enable_mythril=body.enable_mythril,
            )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Task queue unavailable: {exc}",
        ) from exc

    return AsyncScanResponse(
        task_id=result.id,
        status="queued",
        status_url=f"/api/v1/scanner/task/{result.id}",
    )


@router.get(
    "/task/{task_id}",
    response_model=TaskStatusResponse,
    summary="Poll the status of a background scan task",
)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """
    Return the current state of a Celery task.

    States: ``PENDING`` → ``STARTED`` → ``PROGRESS`` → ``SUCCESS`` / ``FAILURE``
    """
    try:
        from celery.result import AsyncResult

        from app.worker import celery_app

        result: AsyncResult = celery_app.AsyncResult(task_id)
        state = result.state
        meta = result.info or {}

        if state == "SUCCESS":
            return TaskStatusResponse(
                task_id=task_id,
                state=state,
                progress=100,
                step="completed",
                result=meta if isinstance(meta, dict) else None,
            )
        if state == "FAILURE":
            return TaskStatusResponse(
                task_id=task_id,
                state=state,
                error=str(meta),
            )
        if isinstance(meta, dict):
            return TaskStatusResponse(
                task_id=task_id,
                state=state,
                progress=meta.get("progress"),
                step=meta.get("step"),
            )
        return TaskStatusResponse(task_id=task_id, state=state)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Task queue unavailable: {exc}",
        ) from exc


@router.post(
    "/scan/report/json",
    summary="Scan and return a JSON audit report",
)
async def scan_report_json(
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Run a scan and return a structured JSON audit report."""
    scan_result = await scan_contract(body, db)
    return generate_json_report(scan_result)


@router.post(
    "/scan/report/html",
    response_class=HTMLResponse,
    summary="Scan and return an HTML audit report",
)
async def scan_report_html(
    body: ScanRequest,
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Run a scan and return a human-readable HTML audit report."""
    scan_result = await scan_contract(body, db)
    html = generate_html_report(scan_result)
    return HTMLResponse(content=html)
