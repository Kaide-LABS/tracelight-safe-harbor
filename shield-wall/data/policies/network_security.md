# Tracelight Network Security Policy
**Version:** 3.0 | **Effective Date:** January 1, 2025 | **Owner:** CISO / Head of Infrastructure

## 1. Purpose
This policy establishes requirements for securing Tracelight network infrastructure, including cloud networking, perimeter defense, segmentation, and monitoring.

## 2. Network Architecture
- All production infrastructure is hosted on AWS in the eu-west-1 (Ireland) region with disaster recovery in eu-central-1 (Frankfurt).
- Production, staging, and development environments are deployed in separate AWS accounts (multi-account strategy) with no network peering between production and non-production.
- Each environment uses dedicated VPCs with non-overlapping CIDR ranges.
- Production VPC: 10.0.0.0/16 with public subnets (load balancers only), private subnets (application tier), and isolated subnets (database tier).

## 3. Network Segmentation
- Network segmentation is enforced via VPC subnets, security groups, and network ACLs.
- The application tier can only communicate with the database tier on specific ports (PostgreSQL 5432, Redis 6379).
- The database tier has no internet access (no NAT gateway, no internet gateway route).
- Inter-service communication uses AWS PrivateLink or VPC endpoints. Public internet routing for internal services is prohibited.
- Kubernetes pods (EKS) use Calico network policies for microsegmentation.

## 4. Perimeter Security
- The only public-facing entry point is the Application Load Balancer (ALB) on port 443 (HTTPS).
- HTTP (port 80) connections are automatically redirected to HTTPS.
- AWS WAF (Web Application Firewall) is deployed on the ALB with rules for: SQL injection, XSS, rate limiting (10,000 requests/minute per IP), geo-blocking (configurable per customer), and bot detection.
- AWS Shield Advanced provides DDoS protection with 24/7 DDoS Response Team (DRT) support.
- Cloudflare is used as CDN and additional DDoS mitigation layer in front of the ALB.

## 5. Firewall and Security Groups
- Security groups follow a deny-all-by-default model. Only explicitly required ports and sources are allowed.
- Production load balancer security group: inbound 443 from 0.0.0.0/0, outbound to application tier on 8080.
- Application tier security group: inbound 8080 from ALB security group only, outbound to database tier on 5432/6379.
- Database tier security group: inbound 5432/6379 from application tier only, no outbound internet access.
- Security group changes require Terraform pull request with security team review.
- AWS Config rules continuously monitor for overly permissive security groups (0.0.0.0/0 on non-443 ports) and auto-remediate.

## 6. DNS and Domain Security
- DNS is managed via AWS Route 53 with DNSSEC enabled.
- Domain registrar accounts are protected with MFA and restricted to the Infrastructure team.
- CAA records restrict certificate issuance to AWS Certificate Manager and Let's Encrypt.

## 7. VPN and Remote Connectivity
- Site-to-site VPN is not used. All connectivity is via Cloudflare Zero Trust (ZTNA).
- Partner API integrations use AWS PrivateLink or IP-whitelisted API Gateway endpoints with mutual TLS.

## 8. Network Monitoring
- VPC Flow Logs are enabled on all VPCs and published to CloudWatch Logs and Splunk SIEM.
- GuardDuty monitors for malicious network activity (port scanning, C2 communication, DNS exfiltration).
- Unusual outbound traffic patterns trigger automated alerts and temporary egress blocking.
- Network throughput and latency are monitored via CloudWatch with alerting thresholds.

## 9. Wireless Security
- Corporate Wi-Fi uses WPA3-Enterprise with certificate-based authentication (802.1X via Okta RADIUS).
- Guest Wi-Fi is segmented from the corporate network with internet-only access and bandwidth throttling.
- Rogue access point detection is enabled via Meraki wireless management.
