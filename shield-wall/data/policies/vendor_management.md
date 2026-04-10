# Tracelight Vendor and Third-Party Risk Management Policy
**Version:** 2.0 | **Effective Date:** January 1, 2025 | **Owner:** CISO / Head of Procurement

## 1. Purpose
This policy governs the assessment, onboarding, monitoring, and offboarding of vendors and third parties that access, process, or store Tracelight data or provide critical services.

## 2. Vendor Risk Assessment
- All vendors are assessed before onboarding using a risk-tiered framework:
  - **Tier 1 (Critical):** Vendors with access to production data or providing critical infrastructure (e.g., AWS, Okta, Splunk). Full security assessment required annually.
  - **Tier 2 (High):** Vendors processing Confidential data or providing important services (e.g., Stripe, Datadog). Security questionnaire and SOC 2 review required annually.
  - **Tier 3 (Standard):** Vendors with Internal data access or non-critical services. Self-assessment questionnaire required at onboarding and biennially.
- Assessment includes: SOC 2 Type II report review, penetration test results (within last 12 months), insurance coverage verification, data processing agreement (DPA) review, and security questionnaire completion.

## 3. Contractual Requirements
- All vendors processing Tracelight data must execute a Data Processing Agreement (DPA) that includes: purpose limitation, data minimization, breach notification obligations (< 48 hours), audit rights, sub-processor disclosure, and data deletion upon termination.
- Vendors handling Restricted data must demonstrate encryption at rest and in transit, access logging, and incident response capabilities.
- SLA requirements: Tier 1 vendors must provide 99.9% uptime SLA with defined penalties. Tier 2 vendors must provide 99.5% uptime SLA.
- Right-to-audit clause is mandatory for Tier 1 and Tier 2 vendors.

## 4. Ongoing Monitoring
- Tier 1 vendors are monitored continuously via SecurityScorecard for changes in security posture.
- Vendor SOC 2 reports are collected and reviewed annually by the Security team.
- Significant changes (acquisitions, breaches, leadership changes) trigger ad-hoc reassessment.
- Vendor access is reviewed quarterly as part of the access review process.

## 5. Vendor Access Controls
- Vendor access to Tracelight systems follows the principle of least privilege.
- Vendor accounts are created in a dedicated organizational unit (OU) with restricted permissions.
- Vendor access is time-limited (maximum 90 days, renewable with approval).
- All vendor access is logged in CloudTrail and monitored by the Security Operations team.
- Vendor remote access uses dedicated jump hosts with session recording enabled.

## 6. Sub-Processor Management
- Vendors must disclose all sub-processors that will access Tracelight data.
- Tracelight reserves the right to object to new sub-processors within 30 days of notification.
- Sub-processors must meet the same security requirements as the primary vendor.

## 7. Vendor Offboarding
- Upon contract termination, vendor access is revoked within 24 hours.
- Vendor must provide a certificate of data destruction within 30 days of termination.
- All vendor-held credentials, keys, and tokens are rotated immediately.
- Offboarding checklist is completed and retained by the Procurement and Security teams.

## 8. Fourth-Party Risk
- Tracelight assesses fourth-party risk (vendor's vendors) for Tier 1 vendors.
- Tier 1 vendor contracts require notification of material changes to their supply chain.
- Annual supply chain risk assessment is conducted by the Security team.
