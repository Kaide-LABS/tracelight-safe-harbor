# Tracelight Access Control Policy
**Version:** 3.2 | **Effective Date:** January 15, 2025 | **Owner:** CISO

## 1. Purpose
This policy establishes requirements for controlling logical and physical access to Tracelight information systems, ensuring that only authorized individuals have access to resources appropriate to their role.

## 2. Authentication Requirements
- All users must authenticate via Okta SSO with multi-factor authentication (MFA) enabled.
- Supported MFA methods: hardware FIDO2 security keys (preferred), TOTP authenticator apps. SMS-based MFA is prohibited.
- Service accounts must use IAM roles with temporary credentials (STS AssumeRole). Long-lived access keys are prohibited in production.
- Session timeout is set to 12 hours for standard users and 1 hour for privileged sessions.
- Failed login attempts are locked after 5 consecutive failures for 30 minutes.

## 3. Authorization and Least Privilege
- Tracelight operates a Role-Based Access Control (RBAC) model with the following standard roles: Viewer, Developer, Operator, Admin, SuperAdmin.
- Users are assigned the minimum permissions required to perform their job functions.
- Production environment access is restricted to the Platform Engineering and SRE teams.
- Developer access to staging is read-write; developer access to production is read-only.
- Database (RDS, DynamoDB) direct access requires explicit approval from the Data Engineering lead and is logged via CloudTrail.
- All IAM policies are defined as code in Terraform, stored in Git, and deployed via CI/CD with mandatory peer review.

## 4. Privileged Access Management (PAM)
- Root account credentials are stored in a hardware security module (HSM) and are never used for day-to-day operations.
- Privileged access requests are submitted via PagerDuty JIT Access workflow. Approval is required from a team lead or security team member.
- Privileged sessions are automatically terminated after 4 hours. Extensions require re-approval.
- All privileged actions are recorded in CloudTrail and reviewed weekly by the Security Operations team.

## 5. User Provisioning and Deprovisioning
- New user accounts are automatically provisioned via SCIM from Workday (HR system) upon hire.
- Role assignment follows the approved role matrix maintained by HR and Security.
- Upon termination, SCIM deprovisioning revokes all access within 1 hour. IT confirms revocation within 4 hours.
- Quarterly access reviews are conducted by department managers. Exceptions are escalated to the CISO.
- Contractor and vendor accounts have a maximum duration of 90 days, renewable with manager approval.

## 6. Remote Access
- Remote access is provided via Cloudflare Zero Trust (ZTNA). Traditional VPN is deprecated.
- All remote sessions are encrypted with TLS 1.3 and require MFA.
- Unmanaged devices (BYOD) are permitted for email and collaboration tools only, with MDM enrollment required.
- SSH access to production servers is brokered via AWS Systems Manager Session Manager. Direct SSH is disabled.

## 7. Physical Access
- Data centers are operated by AWS. Physical access controls are governed by AWS SOC 2 Type II report.
- Tracelight offices use badge-based access control (HID iCLASS) with biometric verification for server rooms.
- Visitor access requires sign-in, escort, and NDA execution. Visitor logs are retained for 1 year.
