import pytest
from backend.agents.drift_detector import detect_drift
from backend.models.schemas import DraftAnswer

def test_mfa_drift():
    ans = DraftAnswer(
        question_id=1,
        answer_text="MFA is required.",
        confidence="high",
        evidence_sources=["telemetry"],
        drift_detected=True,
        drift_detail="MFA is missing for bob",
        needs_human_review=False
    )
    alerts = detect_drift([ans])
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"

def test_no_drift():
    ans = DraftAnswer(
        question_id=2,
        answer_text="Encrypted",
        confidence="high",
        evidence_sources=["telemetry"],
        drift_detected=False,
        needs_human_review=False
    )
    alerts = detect_drift([ans])
    assert len(alerts) == 0
