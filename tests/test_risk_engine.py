"""Tests for the risk scoring engine."""
from __future__ import annotations

import pytest

from app.core.analyzer.risk_engine import calculate_risk_score, _score_to_level
from app.core.scanner.base_scanner import Finding
from app.models.contract import RiskLevel


def _make_finding(severity: str, check: str = "test-check") -> Finding:
    return Finding(tool="slither", check=check, title=check, severity=severity)


class TestCalculateRiskScore:
    def test_no_findings_returns_low(self):
        result = calculate_risk_score([])
        assert result.score == 0.0
        assert result.level == RiskLevel.LOW

    def test_single_high_finding(self):
        findings = [_make_finding("high")]
        result = calculate_risk_score(findings)
        assert result.score > 0
        assert result.level in (RiskLevel.HIGH, RiskLevel.CRITICAL, RiskLevel.MEDIUM)

    def test_multiple_high_findings_have_diminishing_returns(self):
        one_high = calculate_risk_score([_make_finding("high")])
        five_high = calculate_risk_score([_make_finding("high")] * 5)
        # 5 highs should score more than 1 but less than 5×single score
        assert five_high.score > one_high.score
        assert five_high.score < one_high.score * 5

    def test_profile_flags_increase_score(self):
        base = calculate_risk_score([])
        with_flags = calculate_risk_score([], is_proxy=True, has_mint=True, has_ownership=True)
        assert with_flags.score > base.score

    def test_score_clamped_to_100(self):
        many_highs = [_make_finding("high")] * 100
        result = calculate_risk_score(many_highs, is_proxy=True, has_mint=True, has_ownership=True)
        assert result.score <= 100.0

    def test_informational_contributes_minimally(self):
        info_findings = [_make_finding("informational")] * 10
        result = calculate_risk_score(info_findings)
        assert result.score < 5.0

    def test_breakdown_keys_present(self):
        result = calculate_risk_score([_make_finding("medium")])
        assert "severity_counts" in result.breakdown
        assert "final_score" in result.breakdown


class TestScoreToLevel:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0, RiskLevel.LOW),
            (10, RiskLevel.LOW),
            (15, RiskLevel.MEDIUM),
            (40, RiskLevel.HIGH),
            (70, RiskLevel.CRITICAL),
            (100, RiskLevel.CRITICAL),
        ],
    )
    def test_thresholds(self, score: float, expected: RiskLevel):
        assert _score_to_level(score) == expected
