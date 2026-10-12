-- =============================================================================
--  IDRM — 03_indexes.sql
--  Read-path optimisation.  Idempotent: YES.
-- =============================================================================

BEGIN;

-- ---- Foreign keys (Postgres does NOT index these automatically) --------------
CREATE INDEX IF NOT EXISTS ix_identity_manager        ON identity(manager_id);
CREATE INDEX IF NOT EXISTS ix_account_identity        ON account(identity_id);
CREATE INDEX IF NOT EXISTS ix_account_system          ON account(system_id);
CREATE INDEX IF NOT EXISTS ix_entitlement_system      ON entitlement(system_id);
CREATE INDEX IF NOT EXISTS ix_grant_account           ON access_grant(account_id);
CREATE INDEX IF NOT EXISTS ix_grant_entitlement       ON access_grant(entitlement_id);
CREATE INDEX IF NOT EXISTS ix_finding_rule            ON finding(risk_rule_id);
CREATE INDEX IF NOT EXISTS ix_finding_identity        ON finding(identity_id);
CREATE INDEX IF NOT EXISTS ix_finding_account         ON finding(account_id);
CREATE INDEX IF NOT EXISTS ix_finding_grant           ON finding(access_grant_id);
CREATE INDEX IF NOT EXISTS ix_finding_system          ON finding(system_id);
CREATE INDEX IF NOT EXISTS ix_finding_assignee        ON finding(assigned_to);
CREATE INDEX IF NOT EXISTS ix_evidence_finding        ON evidence(finding_id);
CREATE INDEX IF NOT EXISTS ix_review_item_campaign    ON review_item(campaign_id);
CREATE INDEX IF NOT EXISTS ix_review_item_grant       ON review_item(access_grant_id);
CREATE INDEX IF NOT EXISTS ix_review_item_reviewer    ON review_item(reviewer_id);
CREATE INDEX IF NOT EXISTS ix_audit_actor_user        ON audit_event(actor_user_id);
CREATE INDEX IF NOT EXISTS ix_scan_triggered_by       ON scan_run(triggered_by);

-- ---- Hot filter columns -----------------------------------------------------
CREATE INDEX IF NOT EXISTS ix_finding_status_sev      ON finding(status, severity);
CREATE INDEX IF NOT EXISTS ix_finding_detected        ON finding(detected_at DESC);
CREATE INDEX IF NOT EXISTS ix_finding_due             ON finding(due_at) WHERE status IN ('open','in_review');
CREATE INDEX IF NOT EXISTS ix_identity_status         ON identity(employment_status);
CREATE INDEX IF NOT EXISTS ix_identity_risk           ON identity(risk_score DESC);
CREATE INDEX IF NOT EXISTS ix_identity_type           ON identity(identity_type);
CREATE INDEX IF NOT EXISTS ix_account_status          ON account(status);
CREATE INDEX IF NOT EXISTS ix_grant_state             ON access_grant(state);
CREATE INDEX IF NOT EXISTS ix_grant_expires           ON access_grant(expires_at) WHERE state = 'active';

-- ---- Audit trail is append-only and read newest-first ------------------------
CREATE INDEX IF NOT EXISTS ix_audit_time              ON audit_event(event_time DESC);
CREATE INDEX IF NOT EXISTS ix_audit_entity            ON audit_event(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_type_time         ON audit_event(event_type, event_time DESC);
CREATE INDEX IF NOT EXISTS ix_audit_correlation       ON audit_event(correlation_id);

-- ---- Trigram search (name / email / username lookups) ------------------------
CREATE INDEX IF NOT EXISTS ix_identity_name_trgm      ON identity   USING gin (display_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_identity_email_trgm     ON identity   USING gin (email        gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_account_username_trgm   ON account    USING gin (username     gin_trgm_ops);

-- ---- JSONB containment for "who changed field X" queries ---------------------
CREATE INDEX IF NOT EXISTS ix_audit_after_gin         ON audit_event USING gin (after_state  jsonb_path_ops);
CREATE INDEX IF NOT EXISTS ix_audit_before_gin        ON audit_event USING gin (before_state jsonb_path_ops);

-- ---- Dormancy / orphan detection --------------------------------------------
CREATE INDEX IF NOT EXISTS ix_account_last_login      ON account(last_login_at)
    WHERE status = 'active';

COMMIT;
