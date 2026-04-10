# Tracelight Data Classification and Protection Policy
**Version:** 2.4 | **Effective Date:** February 1, 2025 | **Owner:** CISO / DPO

## 1. Purpose
This policy defines how Tracelight classifies, handles, stores, transmits, and disposes of data based on sensitivity and regulatory requirements.

## 2. Classification Levels

### 2.1 Public
Data intended for public consumption. No access restrictions. Examples: marketing materials, public documentation, open-source code.

### 2.2 Internal
Data for internal use only. Access restricted to Tracelight employees. Examples: internal wikis, team meeting notes, non-sensitive project documentation. Must not be shared externally without manager approval.

### 2.3 Confidential
Sensitive business data requiring protection. Access restricted to authorized personnel on a need-to-know basis. Examples: financial reports, customer lists, internal audit results, source code, API keys, system architecture diagrams. Must be encrypted at rest (AES-256) and in transit (TLS 1.2+). Sharing requires DLP clearance and manager approval.

### 2.4 Restricted
Highest sensitivity data subject to regulatory requirements. Access strictly controlled with logging and monitoring. Examples: PII (personally identifiable information), PHI (protected health information), payment card data (PCI DSS scope), authentication credentials, encryption keys. Must be encrypted at rest and in transit. Access requires MFA and explicit authorization. Retention and disposal governed by applicable regulations (GDPR, CCPA, PCI DSS, HIPAA).

## 3. Data Handling Requirements

| Requirement | Public | Internal | Confidential | Restricted |
|---|---|---|---|---|
| Encryption at Rest | Optional | Optional | Required (AES-256) | Required (AES-256, CMK) |
| Encryption in Transit | Optional | Required (TLS 1.2+) | Required (TLS 1.2+) | Required (TLS 1.3) |
| Access Control | None | Employee SSO | Need-to-know + MFA | Explicit approval + MFA + logging |
| DLP Monitoring | No | No | Yes | Yes |
| Retention Period | Indefinite | 3 years | 7 years | Per regulation |
| Disposal Method | None | Standard delete | Cryptographic erasure | Cryptographic erasure + certificate |

## 4. Data Loss Prevention (DLP)
- DLP controls are enforced at three layers: network (Zscaler Internet Access), endpoint (CrowdStrike Falcon), and SaaS (Microsoft Purview).
- Policies detect and block unauthorized transmission of Confidential and Restricted data via email, web uploads, USB, and cloud storage.
- DLP violations trigger automated alerts to the Security Operations team and the employee's manager.
- USB mass storage is disabled on all corporate-managed endpoints via Jamf MDM.
- Screen capture and clipboard sharing are restricted in production admin consoles.

## 5. Data Retention and Disposal
- Data retention schedules are maintained by the Legal and Compliance team and reviewed annually.
- Financial records: 7 years (SOX compliance).
- Customer PII: retained only for the duration of the service agreement plus 30 days, then permanently deleted.
- CloudTrail logs: 365 days in hot storage, 7 years in cold storage (Glacier).
- Backup data: retained for 35 days (automated RDS snapshots), then automatically purged.
- Disposal of Restricted data requires cryptographic erasure and a certificate of destruction issued by the Security team.
- Physical media disposal follows NIST SP 800-88 guidelines (degaussing or physical destruction).

## 6. Data Privacy and Regulatory Compliance
- Tracelight processes personal data in accordance with GDPR (EU), CCPA (California), and applicable state privacy laws.
- A Data Protection Officer (DPO) is appointed and reports to the General Counsel.
- Data Processing Agreements (DPAs) are executed with all sub-processors.
- Data Subject Access Requests (DSARs) are fulfilled within 30 days.
- Privacy Impact Assessments (PIAs) are required before launching new products or features that process personal data.
- Cross-border data transfers comply with EU Standard Contractual Clauses (SCCs).

## 7. Labeling and Marking
- All documents and systems must be labeled with the appropriate classification level.
- Email subject lines for Confidential and Restricted data must include the classification tag [CONFIDENTIAL] or [RESTRICTED].
- Source code repositories are labeled Internal by default; repositories containing customer data integrations are labeled Confidential.
