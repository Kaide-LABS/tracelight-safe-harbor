# Tracelight Physical Security Policy
**Version:** 1.3 | **Effective Date:** January 1, 2025 | **Owner:** CISO / Facilities Manager

## 1. Purpose
This policy establishes physical security requirements for Tracelight facilities and the data center infrastructure hosting Tracelight services.

## 2. Data Center Security (AWS)
Tracelight production infrastructure is hosted entirely on Amazon Web Services (AWS). Physical data center security is governed by AWS's SOC 2 Type II report and includes:
- 24/7 security personnel and CCTV surveillance at all data center facilities.
- Multi-factor physical access controls: badge access, biometric scanning, and mantrap entry.
- Environmental controls: fire suppression (FM-200), temperature/humidity monitoring, redundant power (UPS + diesel generators), flood detection.
- Visitor access requires pre-approval, government-issued ID verification, and escort at all times.
- Media destruction: decommissioned storage media is degaussed and physically destroyed per NIST SP 800-88 and DoD 5220.22-M standards.
- AWS data centers are certified: SOC 1/2/3, ISO 27001, ISO 27017, ISO 27018, PCI DSS Level 1, HIPAA, FedRAMP.
- Tracelight reviews AWS's SOC 2 Type II report annually and monitors AWS's compliance certifications.

## 3. Office Security
- Tracelight offices use badge-based access control (HID iCLASS SE) with unique badges per employee.
- Server rooms and network closets require additional biometric verification (fingerprint).
- CCTV cameras monitor all entry/exit points, server rooms, and common areas. Footage retained for 90 days.
- Clean desk policy: employees must secure sensitive materials in locked drawers when leaving their workspace.
- Visitor management: all visitors must sign in at reception, receive a visitor badge, and be escorted. Visitor logs retained for 1 year.

## 4. Endpoint Security
- All corporate laptops and workstations are managed via Jamf (macOS) or Microsoft Intune (Windows).
- Full-disk encryption is enforced: FileVault (macOS), BitLocker (Windows). Compliance verified via MDM.
- Automatic screen lock after 5 minutes of inactivity.
- USB mass storage devices are disabled via MDM policy.
- Anti-malware: CrowdStrike Falcon deployed on all endpoints with real-time protection and EDR.
- Patch management: OS patches applied within 7 days of release. Critical security patches within 48 hours. Compliance enforced via MDM.

## 5. Mobile Device Security
- Mobile devices accessing corporate data must be enrolled in MDM (Jamf or Intune).
- Minimum requirements: device encryption enabled, screen lock (6-digit PIN or biometric), latest OS version (n-1 permitted).
- Remote wipe capability enabled for all enrolled devices.
- Jailbroken or rooted devices are blocked from accessing corporate resources.

## 6. Secure Disposal
- Corporate devices are wiped (cryptographic erasure) before reassignment or disposal.
- Devices beyond useful life are sent to certified e-waste recyclers (R2 certified).
- Paper documents containing Confidential or Restricted information are shredded on-site (cross-cut shredder, DIN 66399 Level P-4).
- Certificates of destruction are retained for 3 years.

## 7. Environmental Controls (Office)
- Fire suppression: sprinkler systems and fire extinguishers per local building code.
- Server room: precision cooling, UPS for graceful shutdown, smoke detection with automated alerting.
- No food or drink permitted in server rooms or network closets.
