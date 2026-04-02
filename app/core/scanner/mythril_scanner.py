"""Mythril symbolic-execution scanner integration."""
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

# Mythril severity levels to canonical severity
_SEVERITY_MAP: Dict[str, str] = {
    "High": "high",
    "Medium": "medium",
    "Low": "low",
}


class MythrilScanner(BaseScanner):
    """
    Wraps the Mythril CLI (``myth``) for deep symbolic-execution analysis.

    Mythril must be installed: ``pip install mythril``.
    Analysis runs against a temporary .sol file and output is parsed from JSON.
    """

    async def scan_source(self, source_code: str, compiler_version: str = "0.8.19") -> ScanResult:
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
        cmd = [
            "myth",
            "analyze",
            file_path,
            "--solv",
            compiler_version,
            "-o",
            "json",
        ]

        log.info("mythril_scan_start", file=file_path)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=settings.mythril_timeout
            )
        except asyncio.TimeoutError:
            log.error("mythril_timeout", file=file_path)
            return ScanResult(tool="mythril", success=False, error="Mythril timed out")
        except FileNotFoundError:
            log.error("mythril_not_found")
            return ScanResult(
                tool="mythril",
                success=False,
                error="mythril not installed; run: pip install mythril",
            )

        raw_stdout = stdout.decode("utf-8", errors="replace")
        raw_stderr = stderr.decode("utf-8", errors="replace")

        log.debug("mythril_raw_output", returncode=proc.returncode, stderr=raw_stderr[:500])

        return self._parse_output(raw_stdout, raw_stderr, proc.returncode)

    def _parse_output(self, stdout: str, stderr: str, returncode: int) -> ScanResult:
        findings: List[Finding] = []

        # Exit code 3 means vulnerabilities found; 0 means no issues
        if returncode not in (0, 3):
            return ScanResult(
                tool="mythril",
                success=False,
                raw_output=stdout,
                error=f"Mythril exited with code {returncode}. stderr: {stderr[:300]}",
            )

        try:
            data: Dict[str, Any] = json.loads(stdout)
        except json.JSONDecodeError:
            # No issues found or non-JSON output
            return ScanResult(tool="mythril", success=True, findings=[], raw_output=stdout)

        for issue in data.get("issues", []):
            findings.append(self._issue_to_finding(issue))

        log.info("mythril_scan_complete", findings=len(findings))
        return ScanResult(
            tool="mythril",
            success=True,
            findings=findings,
            raw_output=stdout,
        )

    @staticmethod
    def _issue_to_finding(issue: Dict[str, Any]) -> Finding:
        severity = _SEVERITY_MAP.get(issue.get("severity", ""), "low")

        locations: list = issue.get("locations", [])
        file_path: str | None = None
        line_start: int | None = None

        if locations:
            src = locations[0].get("sourceMap", "")
            # sourceMap format: "offset:length:fileIndex"
            # Mythril also provides 'filename' in some versions
            file_path = issue.get("filename")
            if src:
                parts = src.split(":")
                try:
                    line_start = int(parts[0])
                except (IndexError, ValueError):
                    pass

        return Finding(
            tool="mythril",
            check=f"SWC-{issue.get('swc-id', 'unknown')}",
            title=issue.get("title", "Unknown Issue"),
            severity=severity,
            description=issue.get("description", ""),
            confidence="medium",
            file_path=file_path,
            line_start=line_start,
        )
