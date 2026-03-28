# Security Policy

## Supported Versions

Currently, only the latest release of the 2FA Authenticator is supported with security updates. We highly recommend that users always run the most recent version.

| Version | Supported          |
| ------- | ------------------ |
| >= 1.0  | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within this project, please **do not create a public issue**. Instead, follow these steps to securely disclose the issue:

1. **Email the maintainers** or use the GitHub Security Advisory feature (if enabled). Ensure you provide a clear description of the vulnerability, the conditions under which it occurs, and, if possible, a proof of concept.
2. **Expect acknowledgment** within 48 hours of your report.
3. We will work to identify a fix and coordinate a release timeline with you before making any public disclosure.

Please note that this application stores 2FA secrets locally on the device encrypted using a user-derived master password. Weak master passwords may inherently compromise the vault's security.

### Threat Model
The built-in encrypted vault relies on `cryptography` primitives (PBKDF2 and Fernet). Physical access to the unlocked device or execution of arbitrary malware on the host machine sits outside the threat model we can defend against natively.
