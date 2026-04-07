import pytest
from backend.agents.drift_detector import detect_drift
from backend.models.schemas import DraftAnswer, TelemetryEvidence, PolicyCitation


def _make_answer(qid=1, telemetry=None, citations=None, drift=False, drift_detail=None):
    return DraftAnswer(
        question_id=qid,
        answer_text="Test answer.",
        confidence="high",
        evidence_sources=["both"] if telemetry and citations else ["telemetry"] if telemetry else ["policy"] if citations else ["none"],
        telemetry_evidence=telemetry or [],
        policy_citations=citations or [],
        drift_detected=drift,
        drift_detail=drift_detail,
        needs_human_review=False,
    )


def _make_telemetry(qid, summary, raw_result=None):
    return TelemetryEvidence(
        question_id=qid,
        query_executed="test_query()",
        query_type="mock",
        raw_result=raw_result or {},
        summary=summary,
        timestamp="2026-04-07T00:00:00Z",
        proves="test",
    )


def _make_citation(qid, excerpt):
    return PolicyCitation(
        question_id=qid,
        policy_document="soc2_type2_report.md",
        section="CC6.1",
        excerpt=excerpt,
        relevance_score=0.95,
        chunk_id="test_chunk",
    )


def test_mfa_drift():
    """Policy requires MFA, telemetry shows user without it."""
    ans = _make_answer(
        qid=1,
        telemetry=[_make_telemetry(1, "IAM user bob has MFAEnabled: false", {"users": [{"UserName": "bob", "MFAEnabled": False}]})],
        citations=[_make_citation(1, "MFA is required for all console access")],
    )
    alerts = detect_drift([ans])
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"
    assert alerts[0].question_id == 1
    assert ans.drift_detected is True
    assert ans.needs_human_review is True


def test_encryption_drift():
    """Policy claims AES-256, telemetry shows unencrypted RDS."""
    ans = _make_answer(
        qid=2,
        telemetry=[_make_telemetry(2, "RDS instance is not encrypted", {"StorageEncrypted": False})],
        citations=[_make_citation(2, "All production databases use AES-256 encryption at rest via KMS")],
    )
    alerts = detect_drift([ans])
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"
    assert ans.drift_detected is True


def test_network_drift():
    """Policy restricts public access, SG has port 8080 open to 0.0.0.0/0."""
    ans = _make_answer(
        qid=3,
        telemetry=[_make_telemetry(3, "Security group allows inbound on 8080", {"IpPermissions": [{"FromPort": 8080, "IpRanges": [{"CidrIp": "0.0.0.0/0"}]}]})],
        citations=[_make_citation(3, "No public-facing endpoints except the load balancer on port 443")],
    )
    alerts = detect_drift([ans])
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"


def test_no_drift():
    """Matching policy and telemetry — no alerts."""
    ans = _make_answer(
        qid=4,
        telemetry=[_make_telemetry(4, "All RDS instances encrypted with AES-256", {"StorageEncrypted": True})],
        citations=[_make_citation(4, "All databases use AES-256 encryption at rest")],
    )
    alerts = detect_drift([ans])
    assert len(alerts) == 0
    assert ans.drift_detected is False


def test_generic_drift_from_synthesis():
    """Synthesis agent flagged drift but none of our specific checks match."""
    ans = _make_answer(
        qid=5,
        drift=True,
        drift_detail="Backup retention is 7 days but policy requires 30 days",
    )
    alerts = detect_drift([ans])
    assert len(alerts) == 1
    assert alerts[0].severity == "warning"


def test_deduplication():
    """Same question shouldn't produce duplicate alerts from specific + generic checks."""
    ans = _make_answer(
        qid=6,
        telemetry=[_make_telemetry(6, "MFAEnabled: false for user", {"users": [{"MFAEnabled": False}]})],
        citations=[_make_citation(6, "MFA is required for all users")],
        drift=True,
        drift_detail="MFA not enforced for some users",
    )
    alerts = detect_drift([ans])
    # Should get exactly 1 alert (specific MFA check), not 2
    assert len([a for a in alerts if a.question_id == 6]) == 1
