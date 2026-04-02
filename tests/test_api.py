"""Tests for the FastAPI application endpoints (no DB / external services needed)."""
from __future__ import annotations

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestScanEndpoint:
    def test_missing_body_returns_422(self):
        """Both source_code and address omitted should return 422."""
        with patch("app.api.v1.scanner.ScanService"):
            response = client.post(
                "/api/v1/scanner/scan",
                json={},
            )
        assert response.status_code == 422

    def test_scan_with_source_code(self):
        """Happy-path: source_code provided, service returns a real ScanResponse."""
        from app.schemas.contract import ContractProfileOut, ScanResponse

        mock_result = ScanResponse(
            contract_id=1,
            address=None,
            name=None,
            risk_score=25.0,
            risk_level="medium",
            vulnerability_count=0,
            vulnerabilities=[],
            profile=ContractProfileOut(
                is_proxy=False,
                has_mint=False,
                has_ownership=False,
                creator_address=None,
            ),
            scan_status="completed",
        )

        with patch("app.api.v1.scanner.ScanService") as MockSvc:
            instance = MockSvc.return_value
            instance.scan = AsyncMock(return_value=mock_result)

            response = client.post(
                "/api/v1/scanner/scan",
                json={"source_code": "pragma solidity ^0.8.0; contract Foo {}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] == 25.0
        assert data["risk_level"] == "medium"


class TestRiskEndpoint:
    def test_risk_score_empty_findings(self):
        response = client.post(
            "/api/v1/risk/score",
            json={"findings": [], "is_proxy": False, "has_mint": False, "has_ownership": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 0.0
        assert data["level"] == "low"

    def test_risk_score_with_findings(self):
        response = client.post(
            "/api/v1/risk/score",
            json={
                "findings": [
                    {"tool": "slither", "check": "reentrancy-eth", "severity": "high"},
                    {"tool": "slither", "check": "locked-ether", "severity": "medium"},
                ],
                "is_proxy": False,
                "has_mint": True,
                "has_ownership": False,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["score"] > 0
        assert data["level"] in ("low", "medium", "high", "critical")

    def test_risk_score_breakdown_present(self):
        response = client.post(
            "/api/v1/risk/score",
            json={
                "findings": [{"check": "reentrancy-eth", "severity": "high"}],
            },
        )
        assert response.status_code == 200
        assert "breakdown" in response.json()


class TestWalletEndpoint:
    def test_invalid_address_returns_422(self):
        response = client.get("/api/v1/wallet/not-an-address/intelligence")
        assert response.status_code == 422
