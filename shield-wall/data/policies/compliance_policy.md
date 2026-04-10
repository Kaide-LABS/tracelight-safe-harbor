# Tracelight Compliance and Regulatory Policy
**Version:** 2.3 | **Effective Date:** January 1, 2025 | **Owner:** General Counsel / CISO

## 1. Purpose
This policy establishes Tracelight's compliance framework governing adherence to applicable laws, regulations, industry standards, and contractual obligations.

## 2. Compliance Framework
Tracelight maintains compliance with the following frameworks and regulations:
- **SOC 2 Type II:** Audited annually by Deloitte & Touche LLP. Covers Security, Availability, Confidentiality, and Processing Integrity trust service criteria.
- **GDPR (EU General Data Protection Regulation):** Full compliance for EU customer data. DPO appointed. Data processing records maintained per Article 30.
- **CCPA/CPRA (California Consumer Privacy Act):** Compliance for California residents. Privacy rights honored including right to know, delete, correct, and opt-out.
- **ISO 27001:2022:** Information Security Management System (ISMS) certified. Annual surveillance audits conducted by BSI.
- **PCI DSS v4.0:** SAQ A compliance for payment processing. Tracelight does not store, process, or transmit cardholder data directly — all payment processing is delegated to Stripe (PCI DSS Level 1 certified).
- **HIPAA:** Business Associate Agreements (BAAs) executed with healthcare customers. PHI is encrypted, access-controlled, and audit-logged per HIPAA Security Rule requirements.

## 3. Governance Structure
- **CISO** is responsible for information security policy, risk management, and compliance oversight.
- **DPO (Data Protection Officer)** reports to General Counsel and manages privacy compliance (GDPR, CCPA).
- **Compliance Committee** meets quarterly to review audit findings, regulatory changes, and risk posture. Members: CISO, DPO, General Counsel, VP Engineering, CFO.
- **Board of Directors** receives annual security and compliance briefing.

## 4. Risk Management
- Annual information security risk assessment conducted per ISO 27005 methodology.
- Risk register maintained in Jira with risk owners, impact/likelihood ratings, and treatment plans.
- Risk acceptance requires CISO approval for Medium risks and Board approval for High/Critical risks.
- Third-party penetration testing conducted annually (NCC Group). Findings tracked to closure.
- Continuous vulnerability scanning (Qualys) with risk-based prioritization.

## 5. Audit and Assurance
- External SOC 2 Type II audit conducted annually. Report available to customers under NDA.
- ISO 27001 surveillance audit conducted annually, recertification every 3 years.
- Internal security audits conducted quarterly by the Security team, covering access reviews, policy compliance, and configuration drift.
- Audit findings are tracked in Jira with defined remediation timelines: Critical (30 days), High (60 days), Medium (90 days).

## 6. Regulatory Monitoring
- Legal and Compliance teams monitor regulatory developments in all jurisdictions where Tracelight operates.
- Material regulatory changes are assessed for impact within 30 days of publication.
- Policy updates are implemented within 90 days of new regulatory requirements taking effect.

## 7. Training and Awareness
- All employees complete annual security awareness training (KnowBe4 platform).
- Phishing simulations conducted monthly. Employees who fail simulations receive targeted retraining.
- Role-based training: developers receive secure coding training (OWASP Top 10), engineers receive cloud security training.
- New hire security orientation completed within first week of employment.
- Training completion is tracked and reported to the Compliance Committee quarterly.

## 8. Policy Management
- All security and compliance policies are reviewed and updated annually, or sooner when triggered by regulatory changes, audit findings, or security incidents.
- Policy changes require CISO approval and are communicated to all employees via email and Confluence.
- Policy acknowledgment is required from all employees annually, tracked via DocuSign.
- Policy exceptions require documented justification, compensating controls, and CISO approval with a defined expiration date.
