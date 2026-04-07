from backend.models.schemas import DraftAnswer, DriftAlert

def detect_drift(answers: list[DraftAnswer]) -> list[DriftAlert]:
    alerts = []
    
    for ans in answers:
        if ans.drift_detected:
            # The synthesis agent (GPT-4o) already determined there is drift.
            # We map this to a formal DriftAlert.
            severity = "warning"
            # Basic heuristic for severity based on keywords
            text = (ans.drift_detail or "").lower()
            if "mfa" in text or "encryption" in text or "public" in text or "open" in text:
                severity = "critical"
                
            alerts.append(DriftAlert(
                question_id=ans.question_id,
                severity=severity,
                policy_states="See policy citations for requirements.",
                telemetry_shows=ans.drift_detail or "Telemetry contradicted policy.",
                recommendation="Investigate the affected resources and align them with the policy immediately."
            ))
            ans.needs_human_review = True
            
    return alerts
