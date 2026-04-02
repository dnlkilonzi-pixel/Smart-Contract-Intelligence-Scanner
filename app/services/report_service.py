"""
Report generation service.

Generates a structured JSON audit report and (optionally) an HTML report
from a completed scan result.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from app.schemas.contract import ScanResponse


def generate_json_report(scan: ScanResponse) -> Dict[str, Any]:
    """Build a structured JSON audit report from a ScanResponse."""
    return {
        "report_type": "Smart Contract Security Audit",
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "contract": {
            "id": scan.contract_id,
            "address": scan.address,
            "name": scan.name,
        },
        "risk_summary": {
            "score": scan.risk_score,
            "level": scan.risk_level,
            "vulnerability_count": scan.vulnerability_count,
        },
        "contract_profile": {
            "is_proxy": scan.profile.is_proxy,
            "has_mint": scan.profile.has_mint,
            "has_ownership": scan.profile.has_ownership,
            "creator_address": scan.profile.creator_address,
        },
        "vulnerabilities": [v.model_dump() for v in scan.vulnerabilities],
        "recommendations": _build_recommendations(scan),
    }


def generate_html_report(scan: ScanResponse) -> str:
    """Generate a simple HTML audit report (no external template engine needed)."""
    report_data = generate_json_report(scan)
    vulns_html = ""
    for v in scan.vulnerabilities:
        color = {"high": "#e74c3c", "medium": "#e67e22", "low": "#f1c40f"}.get(
            v.severity, "#95a5a6"
        )
        vulns_html += f"""
        <tr>
          <td style="color:{color};font-weight:bold">{v.severity.upper()}</td>
          <td>{v.check}</td>
          <td>{v.title}</td>
          <td>{v.ai_category or ''}</td>
          <td>{v.file_path or ''}: {v.line_start or ''}</td>
        </tr>"""

    recommendations_html = "".join(
        f"<li>{r}</li>" for r in report_data["recommendations"]
    )

    level_color = {
        "critical": "#c0392b",
        "high": "#e74c3c",
        "medium": "#e67e22",
        "low": "#27ae60",
    }.get(scan.risk_level, "#95a5a6")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Smart Contract Audit Report — {scan.address or scan.contract_id}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
    h1 {{ color: #2c3e50; }} h2 {{ color: #34495e; border-bottom: 1px solid #ccc; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background-color: #2c3e50; color: white; }}
    .score {{ font-size: 2em; font-weight: bold; color: {level_color}; }}
  </style>
</head>
<body>
  <h1>Smart Contract Security Audit Report</h1>
  <p><strong>Generated:</strong> {report_data["generated_at"]}</p>
  <p><strong>Contract:</strong> {scan.address or f"ID {scan.contract_id}"}</p>

  <h2>Risk Summary</h2>
  <p>Risk Score: <span class="score">{scan.risk_score} / 100</span>
     &nbsp; Level: <strong style="color:{level_color}">{scan.risk_level.upper()}</strong></p>

  <h2>Contract Profile</h2>
  <ul>
    <li>Proxy / Upgradeable: {scan.profile.is_proxy}</li>
    <li>Has Minting: {scan.profile.has_mint}</li>
    <li>Has Ownership: {scan.profile.has_ownership}</li>
    <li>Creator: {scan.profile.creator_address or 'N/A'}</li>
  </ul>

  <h2>Vulnerabilities ({scan.vulnerability_count})</h2>
  <table>
    <tr><th>Severity</th><th>Check</th><th>Title</th><th>AI Category</th><th>Location</th></tr>
    {vulns_html}
  </table>

  <h2>Recommendations</h2>
  <ul>{recommendations_html}</ul>
</body>
</html>"""


def _build_recommendations(scan: ScanResponse) -> list:
    recs = []
    checks = {v.check for v in scan.vulnerabilities}

    if any("reentrancy" in c for c in checks):
        recs.append("Implement checks-effects-interactions pattern to prevent reentrancy attacks.")
    if any("overflow" in c or "SWC-101" in c for c in checks):
        recs.append("Use SafeMath or Solidity >=0.8 built-in overflow checks.")
    if scan.profile.has_ownership:
        recs.append("Review access control logic; consider multi-sig or time-lock for privileged functions.")
    if scan.profile.is_proxy:
        recs.append("Audit the upgrade mechanism carefully; ensure only authorised callers can upgrade.")
    if scan.profile.has_mint:
        recs.append("Limit minting rights; consider total supply caps and multi-sig approval.")
    if not recs:
        recs.append("No critical issues found; continue regular audits and monitoring.")
    return recs
