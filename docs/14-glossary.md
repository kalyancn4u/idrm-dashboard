# Glossary

## Identity & access

**Account** — a concrete login on a specific system (`aisha.b` on AWS).
One identity may own many accounts.

**Access Grant** — the assignment of one entitlement to one account, with a
justification and optional expiry. This is the object that gets risk-scored and
certified.

**Access Review / Certification** — a periodic exercise in which a human confirms
that a set of grants is still required. Modelled as `review_campaign` +
`review_item`.

**Entitlement** — a role, permission, group or policy defined on a system
(`AWS_IAM_ADMIN`, `SAP_AP_CLERK`). Entitlements are what accounts get.

**Identity** — the governed principal: a person, a contractor, a vendor, a
service account, or a robot. Identity is *who*; account is *how they log in*.

**Least Privilege** — the principle that an identity should hold only the access
needed to do its job.

**Orphaned Account** — an active account belonging to a terminated identity.

**Privileged Account** — an account capable of administrative action
(`account_type = 'privileged'` or an entitlement with `is_privileged = true`).

**Provisioning** — granting access. **Deprovisioning** is removing it.

**RBAC** — Role-Based Access Control. Access is granted via roles rather than to
individuals directly.

**SoD (Segregation of Duties)** — a control preventing one person from holding two
entitlements that together allow fraud or error to go undetected. `SAP_AP_CLERK` +
`SAP_AP_APPROVER` is the classic example.

**Standing Privilege** — a privileged grant with no expiry. High risk; should be
converted to just-in-time.

## Risk

**Dormancy** — an account that has not authenticated within the configured
window (default 90 days).

**Finding** — an instance of a risk rule firing against a real object. Carries a
severity, a status, a risk score, an SLA due date, an assignee, and evidence.

**Risk Rule** — a catalogued detection condition (`RR-SOD-001`). The catalogue is
data; the implementation is Python.

**Risk Score** — 0–100 per identity. Σ (severity points × rule weight) over open
findings, capped at 100.

**Severity** — critical / high / medium / low. Maps to SLA days (7/14/30/90) and
to risk points (30/18/8/3).

**SLA** — the deadline by which a finding must be remediated, derived from severity.

## Audit

**Audit Event** — one row in `audit_event`: who, when, what, before, after.
Append-only. `UPDATE` and `DELETE` are neutralised by PostgreSQL rules.

**Before/After State** — full `JSONB` snapshots of the row before and after a change.

**Correlation ID** — a UUID grouping all events from one logical request.

**Evidence** — supporting material attached to a finding: a note, a link, a
query, a screenshot, a file.

**Immutable** — cannot be changed or deleted. Enforced at the database level.

**Non-repudiation** — a party cannot deny having performed an action. Provided by
capturing actor username and IP on every write.

**Tamper-evident** — attempts to modify are detectable. IDRM goes further and
makes them *ineffective* (`DO INSTEAD NOTHING`).

## Operations

**HLD** — High-Level Design. The architecture document.

**LLD** — Low-Level Design. The module-and-function document.

**PBKDF2** — Password-Based Key Derivation Function 2. IDRM uses
PBKDF2-SHA256 with 600 000 iterations.

**RBAC (console)** — In IDRM, four console roles: `admin`, `analyst`, `auditor`, `viewer`.

**Scan Run** — one execution of the risk engine, recorded in `scan_run`.

**Trigram Index** — a `pg_trgm` GIN index enabling fast `ILIKE '%term%'` search.

**WCAG AAA** — Web Content Accessibility Guidelines, level AAA. Requires ≥ 7:1
contrast for normal text. IDRM's design system meets this.

## Acronyms

| Acronym | Expansion |
|---|---|
| AD | Active Directory |
| API | Application Programming Interface |
| CSRF | Cross-Site Request Forgery |
| CSP | Content Security Policy |
| CSV | Comma-Separated Values |
| GIN | Generalized Inverted Index (PostgreSQL) |
| HRMS | Human Resource Management System |
| IAM | Identity and Access Management |
| IDRM | Identity Data & Risk Management |
| IdP | Identity Provider |
| ITGC | IT General Controls |
| JIT | Just-In-Time (access) |
| JSONB | JSON Binary (PostgreSQL) |
| MFA | Multi-Factor Authentication |
| ORM | Object-Relational Mapper |
| RBAC | Role-Based Access Control |
| RPO | Recovery Point Objective |
| RTO | Recovery Time Objective |
| SLA | Service Level Agreement |
| SoD | Segregation of Duties |
| SSO | Single Sign-On |
| WAL | Write-Ahead Log |
| XSS | Cross-Site Scripting |
