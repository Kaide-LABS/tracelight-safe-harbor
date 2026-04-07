"""
Deterministic Drift Detector — Pure Python, no LLM.

Independently compares telemetry evidence against policy citations
to detect contradictions. Does NOT rely solely on the synthesis agent's
drift_detected flag — it performs its own analysis.
"""

from backend.models.schemas import DraftAnswer, DriftAlert


def detect_drift(answers: list[DraftAnswer]) -> list[DriftAlert]:
    alerts = []

    for ans in answers:
        # Run all independent checks
        alerts.extend(_check_encryption_drift(ans))
        alerts.extend(_check_mfa_drift(ans))
        alerts.extend(_check_logging_drift(ans))
        alerts.extend(_check_network_drift(ans))
        alerts.extend(_check_generic_drift(ans))

    return alerts


def _extract_telemetry_text(ans: DraftAnswer) -> str:
    """Combine all telemetry summaries and raw results into searchable text."""
    parts = []
    for ev in ans.telemetry_evidence:
        parts.append(ev.summary.lower())
        parts.append(str(ev.raw_result).lower())
    return " ".join(parts)


def _extract_policy_text(ans: DraftAnswer) -> str:
    """Combine all policy excerpts into searchable text."""
    return " ".join(c.excerpt.lower() for c in ans.policy_citations)


def _check_encryption_drift(ans: DraftAnswer) -> list[DriftAlert]:
    """Policy claims encryption at rest but telemetry shows unencrypted resources."""
    if not ans.telemetry_evidence or not ans.policy_citations:
        return []

    policy = _extract_policy_text(ans)
    telemetry = _extract_telemetry_text(ans)

    policy_claims_encryption = any(
        kw in policy for kw in ["aes-256", "encryption at rest", "encrypted", "kms"]
    )
    telemetry_shows_unencrypted = any(
        kw in telemetry
        for kw in [
            '"storageencrypted": false',
            '"encrypted": false',
            "storageencrypted: false",
            "not encrypted",
            "encryption: none",
        ]
    )

    if policy_claims_encryption and telemetry_shows_unencrypted:
        ans.drift_detected = True
        ans.needs_human_review = True
        detail = "Policy claims encryption at rest, but telemetry shows unencrypted resources"
        ans.drift_detail = detail
        return [
            DriftAlert(
                question_id=ans.question_id,
                severity="critical",
                policy_states="Encryption at rest required (AES-256 / KMS)",
                telemetry_shows="One or more resources found with encryption disabled",
                recommendation="Enable encryption on all production resources and rotate KMS keys.",
            )
        ]
    return []


def _check_mfa_drift(ans: DraftAnswer) -> list[DriftAlert]:
    """Policy claims MFA required but telemetry shows users without MFA."""
    if not ans.telemetry_evidence or not ans.policy_citations:
        return []

    policy = _extract_policy_text(ans)
    telemetry = _extract_telemetry_text(ans)

    policy_requires_mfa = any(
        kw in policy
        for kw in ["mfa required", "multi-factor", "multi factor", "mfa enforced", "mfa is required"]
    )
    telemetry_shows_no_mfa = any(
        kw in telemetry
        for kw in [
            '"mfaenabled": false',
            "mfaenabled: false",
            "mfa not enabled",
            "without mfa",
            "no mfa",
        ]
    )

    if policy_requires_mfa and telemetry_shows_no_mfa:
        ans.drift_detected = True
        ans.needs_human_review = True
        detail = "Policy requires MFA for all users, but telemetry shows users without MFA"
        ans.drift_detail = detail
        return [
            DriftAlert(
                question_id=ans.question_id,
                severity="critical",
                policy_states="MFA required for all console and programmatic access",
                telemetry_shows="IAM users found without MFA enabled",
                recommendation="Enforce MFA for all IAM users immediately. Disable console access for non-compliant accounts.",
            )
        ]
    return []


def _check_logging_drift(ans: DraftAnswer) -> list[DriftAlert]:
    """Policy claims comprehensive logging but telemetry shows gaps."""
    if not ans.telemetry_evidence or not ans.policy_citations:
        return []

    policy = _extract_policy_text(ans)
    telemetry = _extract_telemetry_text(ans)

    policy_requires_logging = any(
        kw in policy
        for kw in ["cloudtrail", "all api calls", "comprehensive logging", "audit logging"]
    )
    telemetry_shows_gap = any(
        kw in telemetry
        for kw in [
            "cloudtrail not enabled",
            "logging disabled",
            "no trail",
            "trail status: stopped",
        ]
    )

    if policy_requires_logging and telemetry_shows_gap:
        ans.drift_detected = True
        ans.needs_human_review = True
        detail = "Policy claims comprehensive CloudTrail logging, but gaps detected"
        ans.drift_detail = detail
        return [
            DriftAlert(
                question_id=ans.question_id,
                severity="warning",
                policy_states="All API calls logged via CloudTrail",
                telemetry_shows="CloudTrail logging gaps or disabled trails detected",
                recommendation="Re-enable CloudTrail in all regions and verify log delivery to S3.",
            )
        ]
    return []


def _check_network_drift(ans: DraftAnswer) -> list[DriftAlert]:
    """Policy claims restricted network access but telemetry shows open ports."""
    if not ans.telemetry_evidence or not ans.policy_citations:
        return []

    policy = _extract_policy_text(ans)
    telemetry = _extract_telemetry_text(ans)

    policy_restricts_network = any(
        kw in policy
        for kw in [
            "no public-facing",
            "restricted access",
            "only port 443",
            "load balancer only",
            "no direct public access",
        ]
    )
    telemetry_shows_open = any(
        kw in telemetry
        for kw in [
            "0.0.0.0/0",
            "::/0",
        ]
    )
    # Check specifically for non-443 ports open to the world
    has_non_443_public = False
    for ev in ans.telemetry_evidence:
        raw = str(ev.raw_result).lower()
        if "0.0.0.0/0" in raw and any(
            p in raw for p in ['"fromport": 22', '"fromport": 8080', '"fromport": 3389', '"fromport": 80']
        ):
            has_non_443_public = True
            break

    if policy_restricts_network and telemetry_shows_open and has_non_443_public:
        ans.drift_detected = True
        ans.needs_human_review = True
        detail = "Policy restricts public access, but security groups expose non-443 ports to 0.0.0.0/0"
        ans.drift_detail = detail
        return [
            DriftAlert(
                question_id=ans.question_id,
                severity="warning",
                policy_states="Only HTTPS (443) public-facing via load balancer",
                telemetry_shows="Security groups with non-443 ports open to 0.0.0.0/0",
                recommendation="Restrict inbound security group rules to port 443 only for public-facing resources.",
            )
        ]
    return []


def _check_generic_drift(ans: DraftAnswer) -> list[DriftAlert]:
    """Catch-all: if the synthesis agent flagged drift but none of the specific checks caught it."""
    if ans.drift_detected and not any(
        a.question_id == ans.question_id for a in []
    ):
        # This answer was flagged by the synthesis agent but not by our specific checks.
        # Already handled by the specific checks above if they match, so only create
        # a generic alert if drift_detected is True AND no specific alert was already created.
        # We check this at the caller level to avoid duplicates.
        pass

    # The synthesis agent may have set drift_detected for cases our heuristics don't cover.
    # We promote those to alerts here. The caller (detect_drift) deduplicates.
    if ans.drift_detected and ans.drift_detail:
        # Check if this question already has alerts from specific checks — handled by caller
        severity = "warning"
        text = ans.drift_detail.lower()
        if any(kw in text for kw in ["mfa", "encryption", "public", "open", "unencrypted"]):
            severity = "critical"
        return [
            DriftAlert(
                question_id=ans.question_id,
                severity=severity,
                policy_states="See policy citations for stated requirements",
                telemetry_shows=ans.drift_detail,
                recommendation="Investigate and remediate the infrastructure drift immediately.",
            )
        ]
    return []


# Override detect_drift to deduplicate alerts per question
_original_detect_drift = detect_drift


def detect_drift(answers: list[DraftAnswer]) -> list[DriftAlert]:
    all_alerts = []
    seen_questions = set()

    for ans in answers:
        q_alerts = []
        q_alerts.extend(_check_encryption_drift(ans))
        q_alerts.extend(_check_mfa_drift(ans))
        q_alerts.extend(_check_logging_drift(ans))
        q_alerts.extend(_check_network_drift(ans))

        if q_alerts:
            # Specific checks found drift — use those, skip generic
            for a in q_alerts:
                if a.question_id not in seen_questions:
                    all_alerts.append(a)
                    seen_questions.add(a.question_id)
        else:
            # No specific drift — check generic (synthesis agent flag)
            generic = _check_generic_drift(ans)
            for a in generic:
                if a.question_id not in seen_questions:
                    all_alerts.append(a)
                    seen_questions.add(a.question_id)

    return all_alerts
