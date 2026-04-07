# SOC 2 Type 2 Report

## CC6.1 - Logical Access Controls
Multi-factor authentication is required for all console access. Users must have strong passwords (minimum 14 characters) rotated every 90 days.

## CC6.6 - Encryption
AES-256 encryption at rest is enforced for all production databases. Data in transit must be protected by TLS 1.2 or higher.

## CC7.2 - Monitoring
All API calls are logged via CloudTrail. Alerts are generated for any unauthorized access attempts.
