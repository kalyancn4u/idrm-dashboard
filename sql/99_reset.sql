-- =============================================================================
--  IDRM — 99_reset.sql
--  DESTRUCTIVE. Drops every IDRM object.
--  Run via:  make db-reset
-- =============================================================================

BEGIN;

-- Rules must go before the table they attach to
DROP RULE IF EXISTS audit_event_no_update ON audit_event;
DROP RULE IF EXISTS audit_event_no_delete ON audit_event;

DROP TABLE IF EXISTS scan_run         CASCADE;
DROP TABLE IF EXISTS audit_event      CASCADE;
DROP TABLE IF EXISTS review_item      CASCADE;
DROP TABLE IF EXISTS review_campaign  CASCADE;
DROP TABLE IF EXISTS evidence         CASCADE;
DROP TABLE IF EXISTS finding          CASCADE;
DROP TABLE IF EXISTS sod_rule         CASCADE;
DROP TABLE IF EXISTS risk_rule        CASCADE;
DROP TABLE IF EXISTS access_grant     CASCADE;
DROP TABLE IF EXISTS entitlement      CASCADE;
DROP TABLE IF EXISTS account          CASCADE;
DROP TABLE IF EXISTS identity         CASCADE;
DROP TABLE IF EXISTS system_app       CASCADE;
DROP TABLE IF EXISTS app_user         CASCADE;

-- Functions
DROP FUNCTION IF EXISTS fn_next_finding_code()        CASCADE;
DROP FUNCTION IF EXISTS fn_finding_before_insert()    CASCADE;
DROP FUNCTION IF EXISTS fn_identity_risk_score(BIGINT) CASCADE;
DROP FUNCTION IF EXISTS fn_recompute_all_risk_scores() CASCADE;
DROP FUNCTION IF EXISTS fn_severity_points(TEXT)      CASCADE;
DROP FUNCTION IF EXISTS fn_sla_due_at(TEXT, TIMESTAMPTZ) CASCADE;
DROP FUNCTION IF EXISTS fn_expire_stale_grants()      CASCADE;
DROP FUNCTION IF EXISTS fn_audit_row()                CASCADE;
DROP FUNCTION IF EXISTS fn_touch_updated_at()         CASCADE;
DROP FUNCTION IF EXISTS fn_current_actor()            CASCADE;

COMMIT;
