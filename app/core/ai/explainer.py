"""
LLM-powered vulnerability explanation layer.

Generates human-readable explanations for vulnerability findings using
OpenAI's API when configured, with a structured rule-based fallback for
offline / key-free environments.

Configuration
-------------
Set ``OPENAI_API_KEY`` and ``LLM_EXPLANATION_ENABLED=true`` in the
environment (or ``.env``) to enable the LLM backend.
"""
from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Rule-based fallback templates
# ---------------------------------------------------------------------------

_FALLBACK_TEMPLATES: Dict[str, str] = {
    "reentrancy": (
        "This contract is vulnerable to reentrancy attacks. An external call is "
        "made before internal state is updated, allowing a malicious contract to "
        "re-enter and drain funds. Mitigation: apply the checks-effects-interactions "
        "pattern or use a reentrancy guard (e.g. OpenZeppelin's ReentrancyGuard)."
    ),
    "integer-overflow": (
        "The contract performs arithmetic that can overflow or underflow. In older "
        "Solidity versions (<0.8.0) this silently wraps around, which can be "
        "exploited to bypass balance/supply checks. Mitigation: use Solidity 0.8+ "
        "(built-in overflow checks) or SafeMath for older versions."
    ),
    "access-control": (
        "A sensitive function lacks adequate access control, meaning any caller "
        "can invoke it. Mitigation: add an `onlyOwner` modifier or role-based "
        "access control (e.g. OpenZeppelin's AccessControl)."
    ),
    "unchecked-return": (
        "The return value of a low-level call (`.call()`, `.send()`, or `.transfer()`) "
        "is not checked. A failed call will be silently ignored, potentially leaving "
        "the contract in an inconsistent state. Mitigation: always check return values "
        "or use `require(success, …)`."
    ),
    "rug-pull": (
        "The contract exhibits patterns commonly seen in rug-pull schemes: "
        "centralised control over liquidity, hidden mint/burn functions, or "
        "unrestricted ownership transfer. Users should treat this contract with "
        "extreme caution."
    ),
}

_DEFAULT_TEMPLATE = (
    "This finding ({check}) with {severity} severity was detected by {tool}. "
    "Review the affected code location carefully and apply the principle of "
    "least privilege, defensive programming, and thorough testing to resolve "
    "the issue."
)


def _rule_based_explanation(
    tool: str,
    check: str,
    title: str,
    description: Optional[str],
    severity: str,
    ai_category: Optional[str],
) -> str:
    """Return a template-driven explanation without calling an LLM."""
    category_key = (ai_category or "").lower().replace(" ", "-").replace("_", "-")
    check_lower = check.lower()

    for key, template in _FALLBACK_TEMPLATES.items():
        if key in category_key or key in check_lower:
            return template

    if description:
        return description

    return _DEFAULT_TEMPLATE.format(check=check, severity=severity, tool=tool)


# ---------------------------------------------------------------------------
# LLM explanation (OpenAI)
# ---------------------------------------------------------------------------

def _build_prompt(
    tool: str,
    check: str,
    title: str,
    description: Optional[str],
    severity: str,
    ai_category: Optional[str],
) -> str:
    return (
        "You are a smart contract security expert. Explain the following vulnerability "
        "finding to a Solidity developer in 2-3 clear sentences. Describe the risk and "
        "suggest a concrete mitigation.\n\n"
        f"Tool: {tool}\n"
        f"Check: {check}\n"
        f"Title: {title}\n"
        f"Severity: {severity}\n"
        f"AI category: {ai_category or 'unknown'}\n"
        f"Description: {description or 'N/A'}\n\n"
        "Explanation:"
    )


# Simple in-process cache keyed by a hash of the prompt to avoid redundant API calls
_explanation_cache: Dict[str, str] = {}


async def generate_explanation(
    tool: str,
    check: str,
    title: str,
    description: Optional[str] = None,
    severity: str = "medium",
    ai_category: Optional[str] = None,
) -> str:
    """
    Generate a human-readable explanation for a vulnerability finding.

    Uses the OpenAI API when ``LLM_EXPLANATION_ENABLED=true`` and
    ``OPENAI_API_KEY`` is set; otherwise falls back to rule-based templates.

    Parameters
    ----------
    tool:        Scanner that raised the finding (e.g. ``"slither"``).
    check:       Machine-readable check id (e.g. ``"reentrancy-eth"``).
    title:       Short human-readable title.
    description: Optional raw description from the scanner.
    severity:    Finding severity level.
    ai_category: AI-classified vulnerability category.

    Returns
    -------
    str
        Plain-text explanation suitable for display in a report.
    """
    cache_key = hashlib.md5(
        json.dumps([tool, check, title, severity, ai_category], sort_keys=True).encode()
    ).hexdigest()

    if cache_key in _explanation_cache:
        return _explanation_cache[cache_key]

    explanation: str

    if settings.llm_explanation_enabled and settings.openai_api_key:
        explanation = await _llm_explanation(
            tool=tool,
            check=check,
            title=title,
            description=description,
            severity=severity,
            ai_category=ai_category,
        )
    else:
        explanation = _rule_based_explanation(
            tool=tool,
            check=check,
            title=title,
            description=description,
            severity=severity,
            ai_category=ai_category,
        )

    _explanation_cache[cache_key] = explanation
    return explanation


async def generate_explanations_batch(
    findings: List[dict],
) -> List[str]:
    """
    Generate explanations for a list of finding dicts in parallel.

    Each dict should contain keys: ``tool``, ``check``, ``title``,
    ``description``, ``severity``, ``ai_category``.
    """
    import asyncio

    tasks = [
        generate_explanation(
            tool=f.get("tool", "unknown"),
            check=f.get("check", "unknown"),
            title=f.get("title", f.get("check", "unknown")),
            description=f.get("description"),
            severity=f.get("severity", "medium"),
            ai_category=f.get("ai_category"),
        )
        for f in findings
    ]
    return list(await asyncio.gather(*tasks))


async def _llm_explanation(
    tool: str,
    check: str,
    title: str,
    description: Optional[str],
    severity: str,
    ai_category: Optional[str],
) -> str:
    """Call the OpenAI chat completions API for an explanation."""
    try:
        import httpx

        prompt = _build_prompt(tool, check, title, description, severity, ai_category)
        payload = {
            "model": settings.openai_model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as exc:
        log.warning("llm_explanation_failed", error=str(exc), check=check)
        # Fall back to rule-based on any error
        return _rule_based_explanation(
            tool=tool,
            check=check,
            title=title,
            description=description,
            severity=severity,
            ai_category=ai_category,
        )
