# Tracelight SOC 2 Type II Compliance Report
**Audit Period:** January 1, 2025 – December 31, 2025
**Auditor:** Deloitte & Touche LLP
**Opinion:** Unqualified — No exceptions noted.

## CC6.1 — Logical Access Controls
Multi-factor authentication (MFA) is required for all console and programmatic access to production systems. All users must authenticate via SSO (Okta) with hardware FIDO2 keys or TOTP as a second factor. Password policy enforces a minimum length of 14 characters, rotation every 90 days, and prevents reuse of the last 24 passwords. Service accounts use short-lived IAM roles with session tokens expiring every 1 hour. Privileged access (admin, root) requires just-in-time (JIT) approval via PagerDuty with automatic revocation after 4 hours.

## CC6.2 — User Provisioning and Deprovisioning
User accounts are provisioned through automated SCIM integration with the corporate HR system (Workday). When an employee is terminated or changes roles, access is revoked within 1 hour via automated SCIM deprovisioning. Quarterly access reviews are conducted by department managers and validated by the Security team. Orphaned accounts are flagged and removed within 24 hours of detection.

## CC6.3 — Role-Based Access Control (RBAC)
Tracelight enforces a least-privilege RBAC model. Production access is restricted to the Platform Engineering team. Developers have read-only access to staging environments. Database access requires explicit approval and is logged. All IAM policies are version-controlled in Terraform and reviewed via pull request before deployment.

## CC6.6 — Encryption
AES-256 encryption at rest is enforced for all production databases (RDS, DynamoDB), S3 buckets, and EBS volumes. KMS customer-managed keys (CMKs) are used with automatic annual rotation enabled. Data in transit is protected by TLS 1.3 (minimum TLS 1.2). Certificate management is automated via AWS Certificate Manager with 90-day rotation. All API endpoints enforce HTTPS; HTTP connections are rejected at the load balancer.

## CC6.7 — Data Loss Prevention
DLP controls are implemented at the network perimeter (Zscaler), endpoint (CrowdStrike Falcon), and SaaS layer (Microsoft Purview). Policies detect and block transmission of PII, PHI, financial data, and credentials. USB storage devices are disabled on all corporate endpoints via MDM (Jamf). Email DLP scanning is enabled for all outbound messages via Microsoft 365 Compliance.

## CC7.1 — Vulnerability Management
Automated vulnerability scanning runs daily (Qualys) across all production and staging environments. Critical vulnerabilities (CVSS ≥ 9.0) must be patched within 48 hours. High vulnerabilities (CVSS 7.0–8.9) within 7 days. Medium within 30 days. Container images are scanned at build time (Snyk) and blocked from deployment if critical CVEs are found. Annual penetration testing is performed by an independent third party (NCC Group).

## CC7.2 — Security Monitoring and Logging
All API calls are logged via AWS CloudTrail with log file integrity validation enabled. CloudTrail logs are stored in a dedicated, immutable S3 bucket with a 365-day retention period. Real-time alerting is configured via CloudWatch and PagerDuty for unauthorized access attempts, privilege escalation, root account usage, and security group modifications. SIEM (Splunk) aggregates logs from all sources with a 90-day hot retention and 1-year cold retention. SOC analysts monitor alerts 24/7.

## CC7.3 — Incident Response
Tracelight maintains a formal Incident Response Plan reviewed and updated annually. The IR team conducts quarterly tabletop exercises and annual red team engagements. Incident severity levels: P1 (critical, 15-minute response SLA), P2 (high, 1-hour response), P3 (medium, 4-hour response). All incidents are documented in Jira with root cause analysis completed within 5 business days. Customers are notified of data breaches within 72 hours per GDPR and within 60 days per state breach notification laws.

## CC7.4 — Change Management
All production changes require a pull request with at least two peer reviews and automated CI/CD pipeline validation (unit tests, integration tests, security scans). Emergency changes follow a fast-track process with post-hoc review within 24 hours. All deployments are blue-green with automatic rollback on health check failure. Infrastructure changes are managed via Terraform with state locking and drift detection.

## CC8.1 — Business Continuity and Disaster Recovery
Tracelight operates in a multi-AZ configuration across AWS eu-west-1 with automated failover. RPO is 1 hour, RTO is 4 hours. Database backups (automated snapshots) are taken every hour and retained for 35 days. Cross-region replication to eu-central-1 provides geographic redundancy. BCP and DR plans are tested annually via full failover drills. Results are documented and reviewed by the executive team.

## CC9.1 — Vendor and Third-Party Risk Management
All vendors with access to production data undergo a security assessment before onboarding, including SOC 2 report review, penetration test results, and data processing agreement (DPA) execution. Vendors are reassessed annually. Critical vendors (AWS, Okta, Splunk) are monitored continuously via SecurityScorecard. Vendor access is limited to the minimum scope required and is revoked upon contract termination.
