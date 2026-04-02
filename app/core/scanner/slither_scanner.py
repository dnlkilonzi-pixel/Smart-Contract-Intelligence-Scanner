"""Slither static-analysis scanner integration."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import Any, Dict, List

import structlog

from app.config import get_settings
from app.core.scanner.base_scanner import BaseScanner, Finding, ScanResult

log = structlog.get_logger(__name__)
settings = get_settings()

# Severity mapping from Slither's internal impact levels to our canonical values
_SEVERITY_MAP: Dict[str, str] = {
    "High": "high",
    "Medium": "medium",
    "Low": "low",
    "Informational": "informational",
    "Optimization": "informational",
}


class SlitherScanner(BaseScanner):
    """
    Wraps the Slither CLI to perform static analysis on Solidity source code.

    Slither must be installed and available on PATH (``pip install slither-analyzer``).
    The scanner writes source to a temporary file, invokes ``slither --json -`` and
    parses the JSON output.
    """

    async def scan_source(self, source_code: str, compiler_version: str = "0.8.19") -> ScanResult:
        """Write source to a temp file and scan it."""
        with tempfile.NamedTemporaryFile(
            suffix=".sol", mode="w", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(source_code)
            tmp_path = tmp.name

        try:
            return await self.scan_file(tmp_path, compiler_version=compiler_version)
        finally:
            os.unlink(tmp_path)

    async def scan_file(self, file_path: str, compiler_version: str = "0.8.19") -> ScanResult:
        """Run Slither against *file_path* and parse findings."""
        cmd = [
            "slither",
            file_path,
            "--json",
            "-",                # emit JSON to stdout
            "--solc-remaps",
            "",
        ]

        env = {**os.environ, "SOLC_VERSION": compiler_version}

        log.info("slither_scan_start", file=file_path)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=settings.slither_timeout
            )
        except asyncio.TimeoutError:
            log.error("slither_timeout", file=file_path)
            return ScanResult(tool="slither", success=False, error="Slither timed out")
        except FileNotFoundError:
            log.error("slither_not_found")
            return ScanResult(
                tool="slither",
                success=False,
                error="slither not installed; run: pip install slither-analyzer",
            )

        raw_stdout = stdout.decode("utf-8", errors="replace")
        raw_stderr = stderr.decode("utf-8", errors="replace")

        log.debug("slither_raw_output", returncode=proc.returncode, stderr=raw_stderr[:500])

        return self._parse_output(raw_stdout, raw_stderr, proc.returncode)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_output(self, stdout: str, stderr: str, returncode: int) -> ScanResult:
        """Parse the JSON output from Slither into Finding objects."""
        # Slither returns exit code 1 even when it finds issues (not errors)
        findings: List[Finding] = []

        try:
            data: Dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError:
            # Slither sometimes emits non-JSON preamble; attempt to locate JSON
            start = stdout.find("{")
            if start == -1:
                return ScanResult(
                    tool="slither",
                    success=False,
                    raw_output=stdout,
                    error=f"Could not parse Slither JSON output. stderr: {stderr[:300]}",
                )
            try:
                data = json.loads(stdout[start:])
            except json.JSONDecodeError:
                return ScanResult(
                    tool="slither",
                    success=False,
                    raw_output=stdout,
                    error="Invalid JSON from Slither",
                )

        if not data.get("success"):
            err_msg = data.get("error") or "Slither analysis failed"
            return ScanResult(
                tool="slither",
                success=False,
                raw_output=stdout,
                error=err_msg,
            )

        for detector in data.get("results", {}).get("detectors", []):
            finding = self._detector_to_finding(detector)
            findings.append(finding)

        log.info("slither_scan_complete", findings=len(findings))
        return ScanResult(
            tool="slither",
            success=True,
            findings=findings,
            raw_output=stdout,
        )

    @staticmethod
    def _detector_to_finding(detector: Dict[str, Any]) -> Finding:
        """Convert a single Slither detector dict into a Finding."""
        severity = _SEVERITY_MAP.get(detector.get("impact", ""), "informational")
        confidence = detector.get("confidence", "unknown")

        # Extract source location from the first element mention
        file_path: str | None = None
        line_start: int | None = None
        line_end: int | None = None

        elements: list = detector.get("elements", [])
        for elem in elements:
            src: Dict = elem.get("source_mapping", {})
            if src.get("filename_relative"):
                file_path = src["filename_relative"]
                line_start = src.get("lines", [None])[0]
                if src.get("lines"):
                    line_end = src["lines"][-1]
                break

        return Finding(
            tool="slither",
            check=detector.get("check", "unknown"),
            title=detector.get("check", "unknown").replace("-", " ").title(),
            severity=severity,
            description=detector.get("description", ""),
            confidence=confidence,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
        )
