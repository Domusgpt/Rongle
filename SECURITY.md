# Security Policy

## Supported Versions

We currently provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

We take the security of Rongle seriously. If you believe you have found a security vulnerability, please report it to us as follows:

1. **Do not open a GitHub issue.** Vulnerabilities should be reported privately.
2. Email your findings to **security@rongle.ai** (placeholder - update with actual email).
3. Include as much detail as possible, including steps to reproduce and potential impact.

### Our Commitment

- We will acknowledge receipt of your report within 48 hours.
- We will provide an estimated timeline for a fix.
- We will notify you once the vulnerability is resolved.
- We will give credit to the researcher (if desired) in our security advisories.

## Security Architecture

Rongle is designed with a "Security by Hardware" philosophy:
- **Hardware Air-Gap:** The target machine has no software connection to the agent.
- **Policy Guardian:** Mandatory command filtering and click-zone restrictions.
- **Immutable Ledger:** Tamper-evident Merkle hash chain for all actions.

For more details, see [Architecture Documentation](docs/ARCHITECTURE.md).
