# Security and responsible deployment

Linkscope is a portfolio application. It is not a security-audited production URL-shortening service.

## Implemented measures

- Argon2id password hashing, HMAC-signed time-limited session JWTs, HttpOnly auth cookies, SameSite=Lax, Secure cookies on HTTPS.
- CSRF checks on authenticated write endpoints, same-origin checks on login/registration when Origin is supplied.
- Owner scoping for link and analytics endpoints.
- Server-side URL scheme validation rejecting credentials, local hostnames and nonpublic literal IP addresses; short codes constrained to a safe allowlist.
- Parametrized SQLAlchemy queries, escaped HTML in dynamic JavaScript tables, Excel-compatible CSV formula escaping.
- Pseudonymous click fingerprints using HMAC rather than storing raw IP addresses.
- Optional Redis-based distributed login, registration and link-creation rate limits; cache invalidation on edits and deletion.
- Production startup rejects default or short JWT secret.

## Important before hosting publicly

1. Add email verification and password recovery.
2. Add abuse reporting and reputation checks to prevent malicious links and phishing.
3. Add account-level audit logging and token/session revocation.
4. Set trusted reverse-proxy and HTTPS settings; configure secure cookies and a restrictive Content Security Policy.
5. Make rate limiting mandatory with failure handling, impose account and storage quotas, and implement event retention.
6. Review privacy/consent requirements, user terms, malware filtering, backups and security monitoring.
7. Commission a security review and test under concurrent PostgreSQL/Redis production workloads.

Never upload `.env`, database files, passwords or private keys to the repository. The seeded account is for disposable local demonstrations only.
