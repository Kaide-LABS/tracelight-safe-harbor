# Tracelight Encryption and Key Management Policy
**Version:** 2.1 | **Effective Date:** January 1, 2025 | **Owner:** CISO / Head of Platform Engineering

## 1. Purpose
This policy defines requirements for cryptographic protection of data at rest, in transit, and in use across all Tracelight systems.

## 2. Encryption at Rest
- All production data stores must be encrypted at rest using AES-256.
- AWS RDS instances: encrypted with AWS KMS customer-managed keys (CMKs). Encryption is enforced at instance creation and cannot be disabled.
- AWS S3 buckets: server-side encryption (SSE-KMS) with CMKs. Bucket policies deny PutObject requests without encryption headers.
- AWS EBS volumes: encrypted with CMKs. Unencrypted volumes are prohibited in production accounts. AWS Config auto-remediates violations.
- AWS DynamoDB tables: encrypted with CMKs using AWS-owned or customer-managed keys.
- Backups and snapshots inherit encryption from their source resources.
- Laptop and workstation full-disk encryption is required (FileVault on macOS, BitLocker on Windows) and enforced via Jamf/Intune MDM.

## 3. Encryption in Transit
- All data in transit must be encrypted using TLS 1.3 (preferred) or TLS 1.2 (minimum). TLS 1.0 and 1.1 are disabled across all endpoints.
- Public API endpoints enforce HTTPS via ALB listener rules. HTTP requests are redirected to HTTPS (301).
- Internal service-to-service communication uses mutual TLS (mTLS) via AWS App Mesh / Istio service mesh.
- Database connections use TLS with certificate verification (rds-ca-rsa2048-g1 CA bundle).
- Email encryption: Microsoft 365 Message Encryption for external emails containing Confidential or Restricted data.

## 4. Key Management
- All encryption keys are managed through AWS Key Management Service (KMS).
- Customer-managed keys (CMKs) are used for production workloads. AWS-managed keys are permitted for non-production only.
- Key rotation: automatic annual rotation is enabled for all CMKs. Manual rotation is performed immediately if key compromise is suspected.
- Key access: IAM policies restrict key usage to specific services and roles. Key administrators cannot use keys for encryption/decryption, and key users cannot administer keys (separation of duties).
- Key deletion: CMKs scheduled for deletion have a 30-day waiting period. Deletion requires CISO approval.
- Hardware Security Modules (HSMs): AWS CloudHSM is used for keys requiring FIPS 140-2 Level 3 compliance.

## 5. Certificate Management
- TLS certificates for public endpoints are provisioned via AWS Certificate Manager (ACM) with automatic renewal.
- Internal certificates are issued by a private CA (AWS Private CA) with 1-year validity and automatic rotation.
- Certificate pinning is not used for web applications but is enforced for mobile API clients.
- Certificate transparency logs are monitored for unauthorized certificate issuance.

## 6. Cryptographic Standards
- Approved algorithms: AES-256 (symmetric), RSA-2048+ or ECDSA P-256+ (asymmetric), SHA-256+ (hashing).
- Prohibited algorithms: DES, 3DES, RC4, MD5, SHA-1.
- Password hashing uses bcrypt with a minimum cost factor of 12, or Argon2id.
- Random number generation uses cryptographically secure PRNGs (e.g., /dev/urandom, AWS KMS GenerateRandom).

## 7. Tokenization and Masking
- Payment card data (PCI scope) is tokenized via Stripe. Tracelight never stores, processes, or transmits raw card numbers.
- PII in non-production environments is masked or replaced with synthetic data.
- Log files are scrubbed to remove sensitive data (credentials, tokens, PII) before ingestion into Splunk.
