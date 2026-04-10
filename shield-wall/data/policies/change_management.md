# Tracelight Change Management Policy
**Version:** 2.5 | **Effective Date:** January 1, 2025 | **Owner:** VP Engineering / CISO

## 1. Purpose
This policy governs changes to Tracelight production systems, ensuring that modifications are authorized, tested, reviewed, and deployed safely with minimal risk to service availability and security.

## 2. Change Categories

### 2.1 Standard Changes
Pre-approved, low-risk changes that follow established procedures. Examples: dependency updates (non-major), configuration tuning within defined parameters, scaling adjustments. Requires: automated CI/CD pipeline approval only.

### 2.2 Normal Changes
Changes requiring review and approval before deployment. Examples: new features, API changes, infrastructure modifications, database schema changes. Requires: pull request with 2 peer reviews, automated tests passing, security scan clear.

### 2.3 Emergency Changes
Critical changes required to resolve P1/P2 incidents or patch actively exploited vulnerabilities. Requires: verbal approval from Engineering Lead or CISO, deployed immediately, post-hoc review within 24 hours.

## 3. Change Process

### 3.1 Development
- All code changes are developed on feature branches and submitted as pull requests (PRs) in GitHub.
- PRs must include: description of changes, testing evidence, rollback plan.
- Automated checks run on every PR: unit tests, integration tests, linting, security scanning (Snyk, CodeQL), license compliance.

### 3.2 Review
- Normal changes require at least 2 peer reviews from team members.
- Changes affecting security controls, IAM policies, or network configuration require Security team review.
- Database migrations require DBA review.
- Infrastructure changes (Terraform) require Infrastructure team review.

### 3.3 Testing
- All changes must pass automated test suites with minimum 80% code coverage.
- Integration tests run against staging environment before production deployment.
- Performance-sensitive changes require load testing results.
- Security-sensitive changes require manual security review or threat modeling.

### 3.4 Deployment
- Production deployments use blue-green deployment strategy via AWS CodeDeploy.
- Health checks validate new deployment within 5 minutes. Automatic rollback on failure.
- Database migrations are forward-only and backward-compatible (expand-and-contract pattern).
- Deployment windows: weekdays 09:00–16:00 UTC (except emergencies). No deployments on Fridays without VP Engineering approval.
- Feature flags (LaunchDarkly) enable gradual rollouts and instant kill switches.

### 3.5 Post-Deployment
- Deployment metrics monitored for 30 minutes post-release: error rates, latency, CPU/memory.
- Anomaly detection triggers automatic rollback if error rate exceeds 2x baseline.
- Deployment artifacts (build ID, commit SHA, deployer, timestamp) are logged in the deployment registry.

## 4. Infrastructure as Code
- All infrastructure is managed via Terraform with version-controlled state in S3.
- Infrastructure changes follow the same PR and review process as application code.
- Terraform plans are generated and reviewed before apply. No manual console changes in production.
- Drift detection runs daily via AWS Config. Drifted resources are flagged and corrected within 48 hours.

## 5. Separation of Duties
- Developers cannot approve their own pull requests.
- Developers cannot deploy their own changes to production (CI/CD pipeline enforces this).
- IAM policy changes require Security team approval separate from the requesting team.
- Root account access is restricted to break-glass scenarios with dual-person authorization.

## 6. Change Advisory Board (CAB)
- Weekly CAB meeting reviews upcoming high-risk changes and post-deployment issues.
- CAB members: VP Engineering, Security Lead, SRE Lead, QA Lead.
- High-risk changes (database migrations, security control changes, major version upgrades) require CAB approval.

## 7. Rollback Procedures
- All deployments have a documented rollback plan.
- Blue-green deployments: rollback by switching traffic back to previous version (< 30 seconds).
- Database changes: rollback via backward-compatible migrations or point-in-time recovery.
- Maximum rollback time target: 5 minutes for application changes, 30 minutes for database changes.
