"""
AI vulnerability classifier.

Uses a scikit-learn RandomForest trained on labelled vulnerability data.
Falls back to a rule-based classifier when the model file is not present
(useful for development / first run).

Categories:
    - Reentrancy
    - Integer Overflow/Underflow
    - Access Control
    - Rug-pull Risk
    - Unchecked Return Value
    - Other
"""
from __future__ import annotations

import os
from typing import List, Optional, Tuple

import joblib
import numpy as np
import structlog
from sklearn.ensemble import RandomForestClassifier

from app.config import get_settings
from app.core.ai.feature_extractor import FEATURE_DIM, extract_batch, extract_features
from app.core.analyzer.vulnerability_parser import CATEGORY_MAP
from app.core.scanner.base_scanner import Finding

log = structlog.get_logger(__name__)
settings = get_settings()

LABELS = [
    "Reentrancy",
    "Integer Overflow/Underflow",
    "Access Control",
    "Rug-pull Risk",
    "Unchecked Return Value",
    "Other",
]


class VulnerabilityClassifier:
    """
    Wraps a scikit-learn classifier for vulnerability category prediction.

    On first use, if no model file exists, a bootstrap model is trained on
    synthetic heuristic-labelled data so that the API remains functional.
    """

    def __init__(self) -> None:
        self._model: Optional[RandomForestClassifier] = None
        self._loaded = False

    def _load_or_bootstrap(self) -> None:
        if self._loaded:
            return

        model_path = settings.ai_model_path
        if os.path.exists(model_path):
            try:
                self._model = joblib.load(model_path)
                log.info("ai_model_loaded", path=model_path)
                self._loaded = True
                return
            except Exception as exc:
                log.warning("ai_model_load_failed", error=str(exc))

        log.info("ai_model_bootstrapping", reason="no model file found")
        self._model = self._train_bootstrap_model()
        self._loaded = True

        # Persist for subsequent runs
        try:
            os.makedirs(os.path.dirname(model_path) or ".", exist_ok=True)
            joblib.dump(self._model, model_path)
            log.info("ai_model_saved", path=model_path)
        except Exception as exc:
            log.warning("ai_model_save_failed", error=str(exc))

    def predict(self, finding: Finding) -> Tuple[str, float]:
        """
        Return (category, confidence) for a single finding.

        Falls back to rule-based lookup if the ML model raises an error.
        """
        self._load_or_bootstrap()

        try:
            features = extract_features(finding).reshape(1, -1)
            assert self._model is not None
            label_idx: int = int(self._model.predict(features)[0])
            proba = float(np.max(self._model.predict_proba(features)))
            return LABELS[label_idx], proba
        except Exception as exc:
            log.warning("ai_predict_failed", error=str(exc))
            return self._rule_based(finding)

    def predict_batch(self, findings: List[Finding]) -> List[Tuple[str, float]]:
        """Predict categories for a list of findings."""
        if not findings:
            return []
        self._load_or_bootstrap()

        try:
            X = extract_batch(findings)
            assert self._model is not None
            label_idxs = self._model.predict(X)
            probas = np.max(self._model.predict_proba(X), axis=1)
            return [(LABELS[int(i)], float(p)) for i, p in zip(label_idxs, probas)]
        except Exception as exc:
            log.warning("ai_predict_batch_failed", error=str(exc))
            return [self._rule_based(f) for f in findings]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _rule_based(finding: Finding) -> Tuple[str, float]:
        """Simple rule-based fallback using the CATEGORY_MAP."""
        category = CATEGORY_MAP.get(finding.check, "Other")
        return category, 0.5  # fixed confidence for rule-based

    @staticmethod
    def _train_bootstrap_model() -> RandomForestClassifier:
        """
        Train a RandomForest on synthetically generated heuristic data.

        Each LABELS class is represented by constructing archetypal feature
        vectors based on known check names and severities.
        """
        from app.core.ai.feature_extractor import _KNOWN_CHECKS, _SEVERITY_MAP

        rng = np.random.default_rng(42)
        X_rows, y_rows = [], []

        # Synthetic data: for each known check create N labelled samples with noise
        check_label_map = {
            "reentrancy-eth": 0,
            "reentrancy-no-eth": 0,
            "reentrancy-benign": 0,
            "SWC-107": 0,
            "integer-overflow": 1,
            "SWC-101": 1,
            "suicidal": 2,
            "controlled-delegatecall": 2,
            "SWC-105": 2,
            "SWC-106": 2,
            "SWC-115": 2,
            "arbitrary-send-eth": 3,
            "arbitrary-send-erc20": 3,
            "unchecked-return-value": 4,
            "SWC-104": 4,
            "locked-ether": 5,
            "tx-origin": 2,
            "SWC-114": 5,
            "SWC-120": 5,
        }

        for check, label in check_label_map.items():
            base_vec = np.zeros(FEATURE_DIM, dtype=np.float32)
            if check in _KNOWN_CHECKS:
                base_vec[4 + _KNOWN_CHECKS.index(check)] = 1.0

            for _ in range(50):
                vec = base_vec.copy()
                vec[1] = rng.integers(0, 4)      # severity
                vec[2] = rng.integers(0, 3)      # confidence
                vec[3] = rng.integers(0, 2)      # has_location
                # Add small Gaussian noise
                vec += rng.normal(0, 0.05, FEATURE_DIM).astype(np.float32)
                X_rows.append(vec)
                y_rows.append(label)

        X = np.vstack(X_rows)
        y = np.array(y_rows)

        clf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
        clf.fit(X, y)
        return clf
