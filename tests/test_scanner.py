"""Tests for the Slither scanner JSON parser (no Slither binary needed)."""
from __future__ import annotations

import json


from app.core.scanner.slither_scanner import SlitherScanner


SLITHER_SUCCESS_OUTPUT = json.dumps(
    {
        "success": True,
        "error": None,
        "results": {
            "detectors": [
                {
                    "check": "reentrancy-eth",
                    "impact": "High",
                    "confidence": "Medium",
                    "description": "Reentrancy in Foo.withdraw()",
                    "elements": [
                        {
                            "source_mapping": {
                                "filename_relative": "Foo.sol",
                                "lines": [10, 15],
                            }
                        }
                    ],
                },
                {
                    "check": "locked-ether",
                    "impact": "Medium",
                    "confidence": "High",
                    "description": "Contract locks ether",
                    "elements": [],
                },
            ]
        },
    }
)

SLITHER_FAILURE_OUTPUT = json.dumps(
    {"success": False, "error": "Compilation failed", "results": {}}
)


class TestSlitherScannerParser:
    def setup_method(self):
        self.scanner = SlitherScanner()

    def test_parses_successful_output(self):
        result = self.scanner._parse_output(SLITHER_SUCCESS_OUTPUT, "", 0)
        assert result.success is True
        assert len(result.findings) == 2

    def test_finding_fields_correct(self):
        result = self.scanner._parse_output(SLITHER_SUCCESS_OUTPUT, "", 0)
        reentrancy = result.findings[0]
        assert reentrancy.check == "reentrancy-eth"
        assert reentrancy.severity == "high"
        assert reentrancy.file_path == "Foo.sol"
        assert reentrancy.line_start == 10

    def test_failure_output_returns_error(self):
        result = self.scanner._parse_output(SLITHER_FAILURE_OUTPUT, "", 1)
        assert result.success is False
        assert result.error is not None

    def test_empty_output_returns_error(self):
        result = self.scanner._parse_output("", "compilation error", 1)
        assert result.success is False

    def test_severity_mapping(self):
        result = self.scanner._parse_output(SLITHER_SUCCESS_OUTPUT, "", 0)
        assert result.findings[0].severity == "high"
        assert result.findings[1].severity == "medium"
