-- =============================================================================
--  IDRM — Identity Data & Risk Management
--  01_schema.sql : core DDL
--  ---------------------------------------------------------------------------
--  Target : PostgreSQL 14+
--  Idempotent : YES (CREATE ... IF NOT EXISTS)
--  Destructive : NO
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Extensions
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- trigram search on names/emails

-- =============================================================================
-- 1. APPLICATION USERS  (people who log into the IDRM console)
-- =============================================================================
CREATE TABLE IF NOT EXISTS app_user (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username        TEXT        NOT NULL UNIQUE,
    email           TEXT        NOT NULL UNIQUE,
    full_name       TEXT        NOT NULL,
    password_hash   TEXT        NOT NULL,
    role            TEXT        NOT NULL
                    CHECK (role IN ('admin', 'auditor', 'analyst', 'viewer')),
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    failed_logins   INTEGER     NOT NULL DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  app_user IS 'Console operators. Distinct from governed identities.';
COMMENT ON COLUMN app_user.role IS 'admin=full control, auditor=read-only assurance, analyst=investigate+annotate, viewer=dashboard only';

-- =============================================================================
-- 2. SYSTEMS  (target applications / resources that hold accounts)
-- =============================================================================
CREATE TABLE IF NOT EXISTS system_app (
    id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code                 TEXT        NOT NULL UNIQUE,
    name                 TEXT        NOT NULL,
    description          TEXT,
    owner_team           TEXT,
    criticality          TEXT        NOT NULL DEFAULT 'medium'
                         CHECK (criticality IN ('low', 'medium', 'high', 'critical')),
    data_classification  TEXT        NOT NULL DEFAULT 'internal'
                         CHECK (data_classification IN ('public', 'internal', 'confidential', 'restricted')),
    is_active            BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE system_app IS 'A governed target system (SAP, AWS, Okta, AD, …).';

-- =============================================================================
-- 3. IDENTITIES  (the humans / non-humans being governed)
-- =============================================================================
CREATE TABLE IF NOT EXISTS identity (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    external_ref        TEXT        UNIQUE,            -- HR system employee id
    display_name        TEXT        NOT NULL,
    email               TEXT,
    identity_type       TEXT        NOT NULL DEFAULT 'employee'
                        CHECK (identity_type IN ('employee', 'contractor', 'vendor',
                                                 'service_account', 'robot')),
    department          TEXT,
    job_title           TEXT,
    manager_id          BIGINT      REFERENCES identity(id) ON DELETE SET NULL,
    employment_status   TEXT        NOT NULL DEFAULT 'active'
                        CHECK (employment_status IN ('active', 'leave', 'terminated')),
    join_date           DATE,
    termination_date    DATE,
    is_privileged       BOOLEAN     NOT NULL DEFAULT FALSE,
    risk_score          NUMERIC(5,2) NOT NULL DEFAULT 0
                        CHECK (risk_score >= 0 AND risk_score <= 100),
    last_reviewed_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_termination_after_join
        CHECK (termination_date IS NULL OR join_date IS NULL OR termination_date >= join_date)
);

COMMENT ON COLUMN identity.risk_score IS '0–100, recomputed by fn_recompute_all_risk_scores().';

-- =============================================================================
-- 4. ACCOUNTS  (an identity's login on a specific system)
-- =============================================================================
CREATE TABLE IF NOT EXISTS account (
    id                      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity_id             BIGINT      NOT NULL REFERENCES identity(id)   ON DELETE CASCADE,
    system_id               BIGINT      NOT NULL REFERENCES system_app(id) ON DELETE CASCADE,
    username                TEXT        NOT NULL,
    account_type            TEXT        NOT NULL DEFAULT 'standard'
                            CHECK (account_type IN ('standard', 'privileged', 'shared',
                                                    'service', 'emergency')),
    status                  TEXT        NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'locked', 'disabled', 'orphaned')),
    mfa_enabled             BOOLEAN     NOT NULL DEFAULT FALSE,
    last_login_at           TIMESTAMPTZ,
    password_last_changed_at TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_account_system_username UNIQUE (system_id, username)
);

COMMENT ON TABLE account IS 'Concrete login on a system. One identity may have many.';

-- =============================================================================
-- 5. ENTITLEMENTS  (roles / permissions / groups defined on a system)
-- =============================================================================
CREATE TABLE IF NOT EXISTS entitlement (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    system_id         BIGINT      NOT NULL REFERENCES system_app(id) ON DELETE CASCADE,
    code              TEXT        NOT NULL,
    name              TEXT        NOT NULL,
    description       TEXT,
    entitlement_type  TEXT        NOT NULL DEFAULT 'role'
                      CHECK (entitlement_type IN ('role', 'permission', 'group', 'policy')),
    risk_level        TEXT        NOT NULL DEFAULT 'low'
                      CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    is_privileged     BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_entitlement_system_code UNIQUE (system_id, code)
);

-- =============================================================================
-- 6. ACCESS GRANTS  (account ↔ entitlement assignment — the heart of the model)
-- =============================================================================
CREATE TABLE IF NOT EXISTS access_grant (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    account_id      BIGINT      NOT NULL REFERENCES account(id)     ON DELETE CASCADE,
    entitlement_id  BIGINT      NOT NULL REFERENCES entitlement(id) ON DELETE CASCADE,
    granted_by      TEXT,
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    state           TEXT        NOT NULL DEFAULT 'active'
                    CHECK (state IN ('active', 'pending', 'revoked', 'expired')),
    justification   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_grant_account_entitlement UNIQUE (account_id, entitlement_id)
);

COMMENT ON TABLE access_grant IS 'Effective assignment of an entitlement to an account. Audited on every change.';

-- =============================================================================
-- 7. RISK RULES  (catalog of detectable conditions)
-- =============================================================================
CREATE TABLE IF NOT EXISTS risk_rule (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code        TEXT        NOT NULL UNIQUE,
    name        TEXT        NOT NULL,
    description TEXT,
    category    TEXT        NOT NULL
                CHECK (category IN ('sod', 'dormancy', 'orphan', 'privilege',
                                    'mfa', 'compliance', 'hygiene')),
    severity    TEXT        NOT NULL DEFAULT 'medium'
                CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    weight      NUMERIC(4,2) NOT NULL DEFAULT 1.0,
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    logic_hint  TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON COLUMN risk_rule.logic_hint IS 'Human-readable description of the detection logic; the implementation lives in app/services/risk_engine.py';

-- =============================================================================
-- 8. SoD RULES  (pairwise toxic combinations within a system)
-- =============================================================================
CREATE TABLE IF NOT EXISTS sod_rule (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    system_id         BIGINT NOT NULL REFERENCES system_app(id)  ON DELETE CASCADE,
    entitlement_a_id  BIGINT NOT NULL REFERENCES entitlement(id) ON DELETE CASCADE,
    entitlement_b_id  BIGINT NOT NULL REFERENCES entitlement(id) ON DELETE CASCADE,
    description       TEXT,
    severity          TEXT   NOT NULL DEFAULT 'high'
                      CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    is_active         BOOLEAN NOT NULL DEFAULT TRUE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_sod_distinct CHECK (entitlement_a_id <> entitlement_b_id),
    CONSTRAINT uq_sod_pair UNIQUE (system_id, entitlement_a_id, entitlement_b_id)
);

-- =============================================================================
-- 9. FINDINGS  (an instance of a rule firing against a real object)
-- =============================================================================
CREATE TABLE IF NOT EXISTS finding (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code            TEXT        NOT NULL UNIQUE,        -- FIND-2025-0001
    risk_rule_id    BIGINT      REFERENCES risk_rule(id)    ON DELETE SET NULL,
    identity_id     BIGINT      REFERENCES identity(id)     ON DELETE CASCADE,
    account_id      BIGINT      REFERENCES account(id)      ON DELETE CASCADE,
    access_grant_id BIGINT      REFERENCES access_grant(id) ON DELETE CASCADE,
    system_id       BIGINT      REFERENCES system_app(id)   ON DELETE SET NULL,
    title           TEXT        NOT NULL,
    description     TEXT,
    severity        TEXT        NOT NULL DEFAULT 'medium'
                    CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status          TEXT        NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'in_review', 'remediated',
                                      'accepted_risk', 'false_positive', 'closed')),
    risk_score      NUMERIC(5,2) NOT NULL DEFAULT 0,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    due_at          TIMESTAMPTZ,
    assigned_to     BIGINT      REFERENCES app_user(id) ON DELETE SET NULL,
    remediated_at   TIMESTAMPTZ,
    remediated_by   BIGINT      REFERENCES app_user(id) ON DELETE SET NULL,
    remediation_note TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE finding IS 'A risk-rule violation. Lifecycle: open → in_review → remediated | accepted_risk | false_positive.';

-- =============================================================================
-- 10. EVIDENCE  (attachments / notes supporting a finding)
-- =============================================================================
CREATE TABLE IF NOT EXISTS evidence (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    finding_id    BIGINT      NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    kind          TEXT        NOT NULL DEFAULT 'note'
                  CHECK (kind IN ('note', 'link', 'file', 'query', 'screenshot')),
    title         TEXT        NOT NULL,
    uri           TEXT,
    content       TEXT,
    sha256        TEXT,
    collected_by  BIGINT      REFERENCES app_user(id) ON DELETE SET NULL,
    collected_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =============================================================================
-- 11. REVIEW CAMPAIGNS  (access certifications)
-- =============================================================================
CREATE TABLE IF NOT EXISTS review_campaign (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code          TEXT        NOT NULL UNIQUE,
    name          TEXT        NOT NULL,
    description   TEXT,
    scope_system_id BIGINT    REFERENCES system_app(id) ON DELETE SET NULL,
    status        TEXT        NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft', 'active', 'completed', 'cancelled')),
    starts_at     TIMESTAMPTZ,
    due_at        TIMESTAMPTZ,
    completed_at  TIMESTAMPTZ,
    created_by    BIGINT      REFERENCES app_user(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS review_item (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    campaign_id     BIGINT      NOT NULL REFERENCES review_campaign(id) ON DELETE CASCADE,
    access_grant_id BIGINT      NOT NULL REFERENCES access_grant(id)    ON DELETE CASCADE,
    reviewer_id     BIGINT      REFERENCES app_user(id) ON DELETE SET NULL,
    decision        TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (decision IN ('pending', 'approve', 'revoke', 'modify', 'abstain')),
    decision_note   TEXT,
    decided_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_review_item UNIQUE (campaign_id, access_grant_id)
);

-- =============================================================================
-- 12. AUDIT EVENTS  (append-only, tamper-evident system of record)
-- =============================================================================
CREATE TABLE IF NOT EXISTS audit_event (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_time      TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_user_id   BIGINT      REFERENCES app_user(id) ON DELETE SET NULL,
    actor_username  TEXT        NOT NULL DEFAULT 'system',
    actor_ip        INET,
    event_type      TEXT        NOT NULL,          -- INSERT / UPDATE / DELETE / LOGIN / SCAN
    entity_type     TEXT,                          -- access_grant / finding / …
    entity_id       BIGINT,
    action          TEXT        NOT NULL,
    before_state    JSONB,
    after_state     JSONB,
    correlation_id  UUID        DEFAULT gen_random_uuid(),
    severity        TEXT        NOT NULL DEFAULT 'info'
                    CHECK (severity IN ('info', 'notice', 'warning', 'critical')),
    message         TEXT
);

COMMENT ON TABLE audit_event IS 'Immutable. UPDATE and DELETE are neutralised by rules in 02_functions_triggers.sql.';

-- =============================================================================
-- 13. SCAN RUNS  (bookkeeping for risk-engine executions)
-- =============================================================================
CREATE TABLE IF NOT EXISTS scan_run (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,
    triggered_by   BIGINT      REFERENCES app_user(id) ON DELETE SET NULL,
    trigger_source TEXT        NOT NULL DEFAULT 'manual'
                   CHECK (trigger_source IN ('manual', 'scheduled', 'api', 'boot')),
    rules_evaluated INTEGER    NOT NULL DEFAULT 0,
    findings_created INTEGER   NOT NULL DEFAULT 0,
    findings_closed  INTEGER   NOT NULL DEFAULT 0,
    status         TEXT        NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'success', 'failed')),
    error_text     TEXT
);

COMMIT;
