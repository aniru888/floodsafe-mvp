# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in FloodSafe, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

### How to Report

Email: **anirudh.mohan0106@gmail.com** (or open a private security advisory on GitHub)

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### What to Expect

- **Acknowledgment** within 48 hours
- **Assessment** within 1 week
- **Fix timeline** communicated after assessment

### Scope

The following are in scope:
- Backend API (`apps/backend/`)
- Frontend application (`apps/frontend/`)
- ML Service (`apps/ml-service/`)
- IoT Ingestion service (`apps/iot-ingestion/`)
- Authentication and authorization flows
- Data storage and handling

### Out of Scope

- Denial of service attacks
- Social engineering
- Third-party services (Supabase, Firebase, Koyeb, Vercel)
- Issues in dependencies (report upstream)

## Supported Versions

| Version | Supported |
|---------|-----------|
| Latest on `master` | Yes |
| Older commits | No |

## Disclosure Policy

We follow coordinated disclosure. Please allow us reasonable time to fix vulnerabilities before public disclosure.
