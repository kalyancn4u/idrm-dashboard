-- =============================================================================
--  IDRM — 02_functions_triggers.sql
--  Server-side intelligence: audit capture, risk scoring, immutability.
--  Idempotent : YES (CREATE OR REPLACE + DROP TRIGGER IF EXISTS)
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- Actor context
--   The application sets:  SET LOCAL idrm.actor = 'alice';
--   before any write it wants attributed. Falls back to 'system'.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_current_actor()
RETURNS TEXT
LANGUAGE sql
STABLE
AS $$
    SELECT COALESCE(NULLIF(current_setting('idrm.actor', true), ''), 'system');
$$;

-- =============================================================================
-- A. updated_at maintenance
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_touch_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'app_user', 'system_app', 'identity', 'account',
        'access_grant', 'finding', 'review_campaign'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_touch_%1$s ON %1$I', t);
        EXECUTE format(
            'CREATE TRIGGER trg_touch_%1$s
             BEFORE UPDATE ON %1$I
             FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()', t);
    END LOOP;
END;
$$;

-- =============================================================================
-- B. Generic row-level audit capture
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_audit_row()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_id      BIGINT;
    v_before  JSONB;
    v_after   JSONB;
    v_action  TEXT := TG_OP;
    v_actor   TEXT := fn_current_actor();
    v_actor_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_id     := NEW.id;
        v_after  := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        v_id     := NEW.id;
        v_before := to_jsonb(OLD);
        v_after  := to_jsonb(NEW);
    ELSE  -- DELETE
        v_id     := OLD.id;
        v_before := to_jsonb(OLD);
    END IF;

    -- Resolve a numeric actor id when the actor string is a username
    SELECT u.id INTO v_actor_id
    FROM app_user u
    WHERE u.username = v_actor
    LIMIT 1;

    INSERT INTO audit_event (
        actor_user_id, actor_username, event_type, entity_type,
        entity_id, action, before_state, after_state, severity, message
    ) VALUES (
        v_actor_id, v_actor, TG_OP, TG_TABLE_NAME,
        v_id, v_action, v_before, v_after,
        CASE WHEN TG_OP = 'DELETE' THEN 'warning' ELSE 'info' END,
        format('%s %s on %s#%s', v_actor, lower(v_action), TG_TABLE_NAME, v_id)
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'identity', 'account', 'access_grant', 'finding',
        'review_campaign', 'review_item', 'evidence'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_audit_%1$s ON %1$I', t);
        EXECUTE format(
            'CREATE TRIGGER trg_audit_%1$s
             AFTER INSERT OR UPDATE OR DELETE ON %1$I
             FOR EACH ROW EXECUTE FUNCTION fn_audit_row()', t);
    END LOOP;
END;
$$;

-- =============================================================================
-- C. Audit-table immutability
--    UPDATE/DELETE become silent no-ops. TRUNCATE still works (ops escape hatch).
-- =============================================================================
DROP RULE IF EXISTS audit_event_no_update ON audit_event;
CREATE RULE audit_event_no_update AS
    ON UPDATE TO audit_event DO INSTEAD NOTHING;

DROP RULE IF EXISTS audit_event_no_delete ON audit_event;
CREATE RULE audit_event_no_delete AS
    ON DELETE TO audit_event DO INSTEAD NOTHING;

-- =============================================================================
-- D. Risk scoring
-- =============================================================================

-- Severity → base points
CREATE OR REPLACE FUNCTION fn_severity_points(p_severity TEXT)
RETURNS NUMERIC
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE p_severity
        WHEN 'critical' THEN 30
        WHEN 'high'     THEN 18
        WHEN 'medium'   THEN 8
        WHEN 'low'      THEN 3
        ELSE 1
    END::NUMERIC;
$$;

-- Score for one identity, derived from its open findings
CREATE OR REPLACE FUNCTION fn_identity_risk_score(p_identity_id BIGINT)
RETURNS NUMERIC
LANGUAGE sql
STABLE
AS $$
    SELECT LEAST(
        COALESCE(
            SUM(
                fn_severity_points(f.severity)
                * COALESCE(rr.weight, 1.0)
            ),
            0
        ),
        100
    )::NUMERIC(5,2)
    FROM finding f
    LEFT JOIN risk_rule rr ON rr.id = f.risk_rule_id
    WHERE f.identity_id = p_identity_id
      AND f.status IN ('open', 'in_review');
$$;

COMMENT ON FUNCTION fn_identity_risk_score IS 'Weighted sum of open/in-review findings, capped at 100.';

-- Recompute every identity in one pass
CREATE OR REPLACE FUNCTION fn_recompute_all_risk_scores()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER := 0;
BEGIN
    WITH scored AS (
        SELECT i.id,
               fn_identity_risk_score(i.id) AS score
        FROM identity i
    )
    UPDATE identity i
       SET risk_score = s.score
      FROM scored s
     WHERE i.id = s.id
       AND i.risk_score IS DISTINCT FROM s.score;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

-- SLA due date from severity
CREATE OR REPLACE FUNCTION fn_sla_due_at(p_severity TEXT, p_from TIMESTAMPTZ DEFAULT now())
RETURNS TIMESTAMPTZ
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT p_from + (CASE p_severity
        WHEN 'critical' THEN INTERVAL '7 days'
        WHEN 'high'     THEN INTERVAL '14 days'
        WHEN 'medium'   THEN INTERVAL '30 days'
        ELSE             INTERVAL '90 days'
    END);
$$;

-- =============================================================================
-- E. Finding code generator   FIND-YYYY-NNNN
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_next_finding_code()
RETURNS TEXT
LANGUAGE plpgsql
AS $$
DECLARE
    v_year TEXT := to_char(now(), 'YYYY');
    v_seq  INTEGER;
BEGIN
    SELECT COALESCE(MAX(SUBSTRING(code FROM 'FIND-\d{4}-(\d+)$')::INTEGER), 0) + 1
      INTO v_seq
      FROM finding
     WHERE code LIKE 'FIND-' || v_year || '-%';

    RETURN format('FIND-%s-%s', v_year, lpad(v_seq::TEXT, 4, '0'));
END;
$$;

-- =============================================================================
-- F. Finding auto-population (code, due date, risk score)
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_finding_before_insert()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.code IS NULL OR NEW.code = '' THEN
        NEW.code := fn_next_finding_code();
    END IF;

    IF NEW.due_at IS NULL THEN
        NEW.due_at := fn_sla_due_at(NEW.severity, COALESCE(NEW.detected_at, now()));
    END IF;

    NEW.risk_score := fn_severity_points(NEW.severity);

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_finding_before_insert ON finding;
CREATE TRIGGER trg_finding_before_insert
    BEFORE INSERT ON finding
    FOR EACH ROW EXECUTE FUNCTION fn_finding_before_insert();

-- =============================================================================
-- G. Grant auto-expiry  (called by the app or a cron)
-- =============================================================================
CREATE OR REPLACE FUNCTION fn_expire_stale_grants()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_count INTEGER;
BEGIN
    UPDATE access_grant
       SET state = 'expired'
     WHERE state = 'active'
       AND expires_at IS NOT NULL
       AND expires_at < now();

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$$;

COMMIT;
