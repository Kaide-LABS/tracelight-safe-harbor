# Tracelight Logging and Monitoring Policy
**Version:** 2.2 | **Effective Date:** January 1, 2025 | **Owner:** CISO / SRE Lead

## 1. Purpose
This policy establishes requirements for logging, monitoring, and alerting across Tracelight systems to ensure security visibility, operational awareness, and compliance with audit requirements.

## 2. Logging Requirements

### 2.1 What Must Be Logged
- All authentication events (successful and failed logins, MFA challenges, password changes, session creation/termination).
- All authorization decisions (access granted, access denied, privilege escalation).
- All API calls to production systems (via AWS CloudTrail and application-level access logs).
- All database queries against Restricted data (via RDS Performance Insights and custom audit logging).
- All administrative actions (user creation/deletion, role changes, security group modifications, key management operations).
- All file access events for Confidential and Restricted data (S3 access logs, DLP events).
- All network events (VPC Flow Logs, WAF logs, DNS query logs).
- All application errors and exceptions with stack traces (excluding PII/credentials).
- All deployment and change management events.

### 2.2 Log Format
- Structured JSON format with mandatory fields: timestamp (ISO 8601 UTC), event_type, actor (user/service), action, resource, result (success/failure), source_ip, request_id.
- Log entries must not contain: passwords, API keys, tokens, credit card numbers, or unmasked PII. Log scrubbing is enforced at the application layer and validated by DLP scanning.

### 2.3 Log Integrity
- CloudTrail log file integrity validation is enabled. Logs are stored in a dedicated, immutable S3 bucket with Object Lock (compliance mode).
- Application logs are shipped via Fluent Bit to Splunk with TLS encryption in transit.
- Log tampering detection: hash-chain validation on CloudTrail digests, Splunk integrity monitoring.

## 3. Log Retention
| Log Source | Hot Storage | Cold Storage | Total Retention |
|---|---|---|---|
| CloudTrail | 90 days (S3) | 7 years (Glacier) | 7 years |
| Application Logs | 90 days (Splunk) | 1 year (S3) | 1 year |
| VPC Flow Logs | 30 days (CloudWatch) | 1 year (S3) | 1 year |
| WAF Logs | 90 days (Splunk) | 1 year (S3) | 1 year |
| Database Audit Logs | 90 days (RDS) | 1 year (S3) | 1 year |
| Authentication Logs | 90 days (Okta + Splunk) | 2 years (S3) | 2 years |

## 4. Monitoring and Alerting

### 4.1 Security Monitoring
- 24/7 Security Operations Center (SOC) staffed by 3 analysts across time zones.
- SIEM (Splunk) correlates events from all log sources with 500+ detection rules.
- AWS GuardDuty enabled for all accounts: detects reconnaissance, instance compromise, credential compromise, and data exfiltration.
- CrowdStrike Falcon endpoint detection and response (EDR) on all corporate devices and production instances.

### 4.2 Alert Categories
| Category | Example | Response SLA | Notification |
|---|---|---|---|
| Critical | Root account login, data exfiltration pattern | 15 minutes | PagerDuty (wake) |
| High | Failed MFA brute force, privilege escalation | 1 hour | PagerDuty + Slack |
| Medium | Unusual login location, security group change | 4 hours | Slack #security-alerts |
| Low | Failed login attempt, minor policy violation | Next business day | Splunk dashboard |

### 4.3 Operational Monitoring
- Infrastructure metrics: CPU, memory, disk, network via CloudWatch with auto-scaling triggers.
- Application metrics: request rate, error rate (5xx), latency (p50, p95, p99) via Datadog.
- SLO monitoring: 99.9% availability target tracked via Datadog SLO dashboard. Burn rate alerts trigger at 2x and 10x normal error rate.
- Synthetic monitoring: Datadog Synthetics runs health checks every 60 seconds from 5 global locations.

## 5. Log Access Controls
- Log access is restricted to the Security Operations team and authorized SRE personnel.
- Log access is itself logged and auditable.
- PII in logs is masked or tokenized. Access to unmasked logs requires DPO approval and is time-limited.
- Production log access requires MFA and is brokered via Okta with JIT access.

## 6. Dashboards and Reporting
- Security dashboard: real-time view of authentication events, threat detections, DLP violations, and compliance metrics.
- Compliance dashboard: audit log completeness, policy violations, access review status.
- Executive monthly security report: incident summary, risk posture trends, compliance status.
- SOC 2 evidence collection is automated via Drata, continuously pulling evidence from CloudTrail, Okta, and Splunk.
