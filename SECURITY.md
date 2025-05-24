# Security Policy

## Supported Versions

We actively support security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability in the WiiM integration, please report it responsibly.

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead, please:

1. **Email**: Send details to [security@example.com] (replace with actual contact)
2. **Subject Line**: "WiiM Integration Security Vulnerability"
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes

### What to Expect

- **Acknowledgment**: We'll acknowledge your report within 48 hours
- **Investigation**: We'll investigate and assess the vulnerability
- **Timeline**: We aim to resolve critical issues within 7 days
- **Credit**: With your permission, we'll credit you in the security advisory

### Security Best Practices for Users

When using the WiiM integration:

1. **Network Security**:

   - Keep your Home Assistant instance on a secure network
   - Use HTTPS for Home Assistant access
   - Consider network segmentation for IoT devices

2. **Integration Security**:

   - Only install from official sources (HACS or this repository)
   - Keep the integration updated to the latest version
   - Review logs for unusual activity

3. **Device Security**:
   - Keep WiiM device firmware updated
   - Use strong WiFi passwords
   - Monitor device access logs if available

### Scope

This security policy covers:

- The WiiM integration code
- Configuration and setup procedures
- Integration with Home Assistant

This policy does NOT cover:

- WiiM device firmware vulnerabilities (report to WiiM directly)
- Home Assistant core vulnerabilities (report to Home Assistant)
- Third-party dependencies (report to respective maintainers)

### Security Updates

Security updates will be:

- Released as soon as possible
- Documented in the CHANGELOG
- Announced in release notes
- Tagged with appropriate severity levels

Thank you for helping keep the WiiM integration secure!
