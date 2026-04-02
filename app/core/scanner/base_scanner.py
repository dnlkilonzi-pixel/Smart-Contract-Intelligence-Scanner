"""Abstract base scanner interface."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Finding:
    """A single vulnerability finding produced by any scanner."""

    tool: str
    check: str
    title: str
    severity: str                    # high | medium | low | informational
    description: str = ""
    confidence: Optional[str] = None
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool,
            "check": self.check,
            "title": self.title,
            "severity": self.severity,
            "description": self.description,
            "confidence": self.confidence,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
        }


@dataclass
class ScanResult:
    """Aggregated result from one scanner run."""

    tool: str
    success: bool
    findings: List[Finding] = field(default_factory=list)
    raw_output: str = ""
    error: Optional[str] = None


class BaseScanner(ABC):
    """Common interface every scanner must implement."""

    @abstractmethod
    async def scan_source(self, source_code: str, compiler_version: str = "0.8.19") -> ScanResult:
        """Analyse Solidity source code and return findings."""

    @abstractmethod
    async def scan_file(self, file_path: str) -> ScanResult:
        """Analyse a .sol file on disk and return findings."""
