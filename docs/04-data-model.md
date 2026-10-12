# Data Model

## 1. Entity-relationship overview

```
                    ┌───────────────┐
                    │  system_app   │  target systems
                    └───────┬───────┘
                            │ 1
              ┌─────────────┼─────────────┐
              │ N           │ N           │ N
      ┌───────▼──────┐ ┌────▼──────┐ ┌────▼────────┐
      │   account    │ │entitlement│ │  sod_rule   │
      └───────┬──────┘ └────┬──────┘ └─────────────┘
              │ 1           │ 1
              │             │
              │  ┌──────────▼────────┐
              └─▶│   access_grant    │◀──┐
                 └─────────┬─────────┘   │
                           │             │
      ┌────────────┐       │             │
      │  identity  │◀──────┘             │
      └─────┬──────┘                     │
            │                            │
            │  ┌──────────────┐          │
            └─▶│   finding    │──────────┘
               └──────┬───────┘
                      │ 1
               ┌──────▼───────┐
               │   evidence   │
               └──────────────┘

      ┌──────────────┐        ┌──────────────┐
      │ review_      │ 1    N │ review_item  │
      │ campaign     ├───────▶│              │
      └──────────────┘        └──────────────┘

      ┌──────────────┐        ┌──────────────┐
      │  app_user    │        │ audit_event  │  ← append-only
      └──────────────┘        └──────────────┘
```

## 2. Table reference

### 2.1 `app_user` — console operators

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT IDENTITY PK | |
| `username` | TEXT UNIQUE NOT NULL | lowercase by convention |
| `email` | TEXT UNIQUE NOT NULL | |
| `full_name` | TEXT NOT NULL | |
| `password_hash` | TEXT NOT NULL | Werkzeug `pbkdf2:sha256:600000`. `'PLACEHOLDER'` until `make passwords` runs |
| `role` | TEXT NOT NULL | `admin` \| `auditor` \| `analyst` \| `viewer` |
| `is_active` | BOOLEAN NOT NULL DEFAULT TRUE | |
| `last_login_at` | TIMESTAMPTZ | |
| `failed_logins` | INTEGER DEFAULT 0 | |
| `locked_until` | TIMESTAMPTZ | reserved for lockout policy |
| `created_at`, `updated_at` | TIMESTAMPTZ | `updated_at` maintained by trigger |

> **Not to be confused with `identity`.** `app_user` is a person who operates the
> console. `identity` is a person (or robot) whose *access* is being governed.

### 2.2 `system_app` — governed target systems

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT PK | |
| `code` | TEXT UNIQUE NOT NULL | e.g. `SAP`, `AWS` |
| `name`, `description` | TEXT | |
| `owner_team` | TEXT | accountable team |
| `criticality` | TEXT | `low` \| `medium` \| `high` \| `critical` |
| `data_classification` | TEXT | `public` \| `internal` \| `confidential` \| `restricted` |
| `is_active` | BOOLEAN DEFAULT TRUE | |

### 2.3 `identity` — governed principals

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT PK | |
| `external_ref` | TEXT UNIQUE | HR employee id |
| `display_name` | TEXT NOT NULL | |
| `email` | TEXT | |
| `identity_type` | TEXT | `employee` \| `contractor` \| `vendor` \| `service_account` \| `robot` |
| `department`, `job_title` | TEXT | |
| `manager_id` | BIGINT FK → identity.id | self-referencing |
| `employment_status` | TEXT | `active` \| `leave` \| `terminated` |
| `join_date`, `termination_date` | DATE | CHECK: termination ≥ join |
| `is_privileged` | BOOLEAN DEFAULT FALSE | |
| `risk_score` | NUMERIC(5,2) 0–100 | recomputed by `fn_recompute_all_risk_scores()` |
| `last_reviewed_at` | TIMESTAMPTZ | |

### 2.4 `account` — a login on a system

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT PK | |
| `identity_id` | BIGINT FK → identity | ON DELETE CASCADE |
| `system_id` | BIGINT FK → system_app | ON DELETE CASCADE |
| `username` | TEXT NOT NULL | UNIQUE with `system_id` |
| `account_type` | TEXT | `standard` \| `privileged` \| `shared` \| `service` \| `emergency` |
| `status` | TEXT | `active` \| `locked` \| `disabled` \| `orphaned` |
| `mfa_enabled` | BOOLEAN DEFAULT FALSE | |
| `last_login_at` | TIMESTAMPTZ | drives dormancy detection |
| `password_last_changed_at` | TIMESTAMPTZ | drives rotation detection |

### 2.5 `entitlement` — a role/permission on a system

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT PK | |
| `system_id` | BIGINT FK | |
| `code` | TEXT NOT NULL | UNIQUE with `system_id` |
| `name`, `description` | TEXT | |
| `entitlement_type` | TEXT | `role` \| `permission` \| `group` \| `policy` |
| `risk_level` | TEXT | `low` \| `medium` \| `high` \| `critical` |
| `is_privileged` | BOOLEAN DEFAULT FALSE | |

### 2.6 `access_grant` — the core junction

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT PK | |
| `account_id` | BIGINT FK → account | |
| `entitlement_id` | BIGINT FK → entitlement | |
| `granted_by` | TEXT | who approved it |
| `granted_at` | TIMESTAMPTZ DEFAULT now() | |
| `expires_at` | TIMESTAMPTZ | NULL = standing privilege (a risk) |
| `last_used_at` | TIMESTAMPTZ | drives staleness detection |
| `state` | TEXT | `active` \| `pending` \| `revoked` \| `expired` |
| `justification` | TEXT | business reason |

UNIQUE `(account_id, entitlement_id)`.

### 2.7 `risk_rule` — detection catalogue

| Column | Type | Notes |
|---|---|---|
| `code` | TEXT UNIQUE | `RR-SOD-001` |
| `name`, `description` | TEXT | |
| `category` | TEXT | `sod` \| `dormancy` \| `orphan` \| `privilege` \| `mfa` \| `compliance` \| `hygiene` |
| `severity` | TEXT | assigned to every finding the rule raises |
| `weight` | NUMERIC(4,2) | multiplies severity points in identity scoring |
| `is_active` | BOOLEAN | |
| `logic_hint` | TEXT | human-readable description of the detection logic |

### 2.8 `sod_rule` — toxic entitlement pairs

| Column | Type | Notes |
|---|---|---|
| `system_id` | BIGINT FK | |
| `entitlement_a_id`, `entitlement_b_id` | BIGINT FK | CHECK: a ≠ b |
| `description` | TEXT | why the pair is toxic |
| `severity` | TEXT | |

### 2.9 `finding` — a rule violation

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT PK | |
| `code` | TEXT UNIQUE | `FIND-YYYY-NNNN`, generated by trigger |
| `risk_rule_id` | BIGINT FK | |
| `identity_id`, `account_id`, `access_grant_id`, `system_id` | BIGINT FK | nullable — context depends on the rule |
| `title`, `description` | TEXT | |
| `severity` | TEXT | inherited from the rule at insert time |
| `status` | TEXT | `open` \| `in_review` \| `remediated` \| `accepted_risk` \| `false_positive` \| `closed` |
| `risk_score` | NUMERIC(5,2) | points from `fn_severity_points` |
| `detected_at` | TIMESTAMPTZ DEFAULT now() | |
| `due_at` | TIMESTAMPTZ | set from SLA table by trigger |
| `assigned_to` | BIGINT FK → app_user | |
| `remediated_at`, `remediated_by`, `remediation_note` | | |

### 2.10 `evidence` — supporting material

| Column | Type | Notes |
|---|---|---|
| `finding_id` | BIGINT FK ON DELETE CASCADE | |
| `kind` | TEXT | `note` \| `link` \| `file` \| `query` \| `screenshot` |
| `title` | TEXT NOT NULL | |
| `uri`, `content` | TEXT | |
| `sha256` | TEXT | integrity hash |
| `collected_by` | BIGINT FK → app_user | |
| `collected_at` | TIMESTAMPTZ | |

### 2.11 `review_campaign` / `review_item`

`review_campaign`: `code`, `name`, `description`, `scope_system_id`, `status`
(`draft`/`active`/`completed`/`cancelled`), `starts_at`, `due_at`, `completed_at`, `created_by`.

`review_item`: `campaign_id`, `access_grant_id` (UNIQUE together), `reviewer_id`,
`decision` (`pending`/`approve`/`revoke`/`modify`/`abstain`), `decision_note`, `decided_at`.

### 2.12 `audit_event` — append-only

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT IDENTITY PK | |
| `event_time` | TIMESTAMPTZ DEFAULT now() | |
| `actor_user_id` | BIGINT FK → app_user | NULL for system |
| `actor_username` | TEXT NOT NULL DEFAULT 'system' | |
| `actor_ip` | INET | |
| `event_type` | TEXT | `INSERT`/`UPDATE`/`DELETE`/`LOGIN`/`LOGOUT`/`SCAN`/`EXPORT`/`VIEW` |
| `entity_type` | TEXT | table name |
| `entity_id` | BIGINT | |
| `action` | TEXT | human-readable |
| `before_state` | JSONB | full row snapshot |
| `after_state` | JSONB | full row snapshot |
| `correlation_id` | UUID | groups events from one request |
| `severity` | TEXT | `info`/`notice`/`warning`/`critical` |
| `message` | TEXT | |

**UPDATE and DELETE are neutralised by rules.** Only INSERT works.

### 2.13 `scan_run` — engine bookkeeping

`started_at`, `finished_at`, `triggered_by`, `trigger_source`, `rules_evaluated`,
`findings_created`, `findings_closed`, `status`, `error_text`.

## 3. Relationship cardinalities

| From | To | Cardinality | On delete |
|---|---|---|---|
| identity | identity (manager) | N : 1 | SET NULL |
| identity | account | 1 : N | CASCADE |
| system_app | account | 1 : N | CASCADE |
| system_app | entitlement | 1 : N | CASCADE |
| account | access_grant | 1 : N | CASCADE |
| entitlement | access_grant | 1 : N | CASCADE |
| identity | finding | 1 : N | CASCADE |
| finding | evidence | 1 : N | CASCADE |
| review_campaign | review_item | 1 : N | CASCADE |
| access_grant | review_item | 1 : N | CASCADE |
| app_user | audit_event | 1 : N | SET NULL |

## 4. Views

| View | Purpose |
|---|---|
| `v_identity_risk` | identity + open finding counts + recalculated score |
| `v_open_findings` | findings joined to identity, system, rule |
| `v_grant_detail` | grants joined to identity, system, entitlement |
| `v_dormant_accounts` | active accounts past the dormancy threshold |
| `v_orphan_accounts` | active accounts of terminated identities |
| `v_privileged_without_mfa` | privileged active accounts with `mfa_enabled = false` |
| `v_sod_conflicts` | identity × toxic entitlement pair |
| `v_campaign_progress` | campaign + decided/total/percent |
| `v_kpi_summary` | one-row dashboard aggregate |

## 5. Functions

| Function | Signature | Returns |
|---|---|---|
| `fn_current_actor()` | → TEXT | current `idrm.actor` setting |
| `fn_touch_updated_at()` | TRIGGER | sets `NEW.updated_at = now()` |
| `fn_audit_row()` | TRIGGER | inserts an `audit_event` row |
| `fn_severity_points(severity)` | TEXT → NUMERIC | 30 / 18 / 8 / 3 |
| `fn_identity_risk_score(id)` | BIGINT → NUMERIC | weighted sum, capped at 100 |
| `fn_recompute_all_risk_scores()` | → INTEGER | rows updated |
| `fn_sla_due_at(severity, from)` | → TIMESTAMPTZ | due date from severity |
| `fn_next_finding_code()` | → TEXT | `FIND-YYYY-NNNN` |
| `fn_finding_before_insert()` | TRIGGER | code, due date, risk score |
| `fn_expire_stale_grants()` | → INTEGER | rows expired |

## 6. Sample data at a glance

After `make seed`:

| Table | Rows | Notable content |
|---|---|---|
| `app_user` | 4 | admin, auditor, analyst, viewer |
| `system_app` | 8 | SAP, AWS, OKTA, AD, SALES, WORK, GH, JIRA |
| `identity` | 18 | employees, a contractor, a vendor, 2 service accounts, 2 terminated |
| `account` | ~29 | incl. dormant, MFA-less, shared, service |
| `entitlement` | 31 | roles, permissions, groups, policies |
| `access_grant` | ~40 | incl. standing privilege, unused grants, terminated identities still holding access |
| `risk_rule` | 13 | SoD, dormancy, orphan, privilege, MFA, hygiene, compliance |
| `sod_rule` | 12 | toxic pairs per system |
| `finding` | 18 | across all severities and statuses |
| `evidence` | 5 | notes, a query, a link |
| `review_campaign` | 2 | one active, one completed |
| `review_item` | ~12 | mixed decisions |
| `scan_run` | 10 | historical runs |
| `audit_event` | 0 → grows | populated by every change thereafter |

The dataset is deliberately *risky*: a terminated engineer still holds AWS and
GitHub admin, two SoD conflicts exist in Finance and HR, and a privileged
account has no MFA. That is what makes the demo screens interesting.

## 7. Next

→ [Database Guide](05-database-guide.md)

