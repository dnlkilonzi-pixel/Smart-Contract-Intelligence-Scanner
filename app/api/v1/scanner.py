"""
/api/v1/scanner — contract scanning endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.schemas.contract import ScanRequest, ScanResponse
from app.services.report_service import generate_html_report, generate_json_report
from app.services.scan_service import ScanService

router = APIRouter(prefix="/scanner", tags=["scanner"])


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
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan failed: {exc}",
        ) from exc

    return result


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
