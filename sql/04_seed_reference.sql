-- =============================================================================
--  IDRM — 04_seed_reference.sql
--  Reference / catalog data.  Idempotent: YES (ON CONFLICT DO NOTHING).
-- =============================================================================

BEGIN;

-- =============================================================================
-- SYSTEMS
-- =============================================================================
INSERT INTO system_app (code, name, description, owner_team, criticality, data_classification)
VALUES
    ('SAP',    'SAP S/4HANA',      'ERP — finance, procurement, supply chain', 'ERP Platform',  'critical', 'restricted'),
    ('AWS',    'AWS Production',   'Cloud infrastructure & IAM',               'Cloud Platform','critical', 'restricted'),
    ('OKTA',   'Okta Workforce',   'Identity provider / SSO',                  'IAM Team',      'critical', 'confidential'),
    ('AD',     'Active Directory', 'On-prem directory services',               'Infra Ops',     'high',     'confidential'),
    ('SALES',  'Salesforce',       'CRM — customer & pipeline data',           'RevOps',        'high',     'confidential'),
    ('WORK',   'Workday',          'HRMS — employee records',                  'People Ops',    'high',     'restricted'),
    ('GH',     'GitHub Enterprise','Source control & CI/CD',                   'DevEx',         'high',     'confidential'),
    ('JIRA',   'Jira / Confluence','Project & knowledge management',           'DevEx',         'medium',   'internal')
ON CONFLICT (code) DO NOTHING;

-- =============================================================================
-- ENTITLEMENTS
-- =============================================================================
INSERT INTO entitlement (system_id, code, name, description, entitlement_type, risk_level, is_privileged)
SELECT s.id, v.code, v.name, v.description, v.etype, v.risk, v.priv
FROM (VALUES
    -- SAP
    ('SAP',  'SAP_AP_CLERK',      'AP Clerk',                'Create vendor invoices',              'role',       'medium',   FALSE),
    ('SAP',  'SAP_AP_APPROVER',   'AP Approver',             'Approve vendor payments',             'role',       'high',     FALSE),
    ('SAP',  'SAP_VENDOR_MASTER', 'Vendor Master Maintainer','Create/modify vendor master records', 'role',       'critical', TRUE),
    ('SAP',  'SAP_GL_POST',       'GL Accountant',           'Post general ledger entries',         'role',       'high',     FALSE),
    ('SAP',  'SAP_FI_ADMIN',      'FI Administrator',        'Full finance configuration',          'role',       'critical', TRUE),
    -- AWS
    ('AWS',  'AWS_READONLY',      'ReadOnlyAccess',          'Read-only across all services',       'policy',     'medium',   FALSE),
    ('AWS',  'AWS_POWERUSER',     'PowerUserAccess',         'Full access except IAM',              'policy',     'high',     FALSE),
    ('AWS',  'AWS_IAM_ADMIN',     'IAMFullAccess',           'Manage users, roles, policies',       'policy',     'critical', TRUE),
    ('AWS',  'AWS_S3_DELETE',     'S3 Bucket Delete',        'Delete objects and buckets',          'permission', 'high',     FALSE),
    ('AWS',  'AWS_BILLING',       'Billing Console',         'View and modify billing',             'policy',     'medium',   FALSE),
    -- Okta
    ('OKTA', 'OKTA_USER_ADMIN',   'User Administrator',      'Manage users and groups',             'role',       'high',     TRUE),
    ('OKTA', 'OKTA_APP_ADMIN',    'Application Administrator','Manage app integrations',             'role',       'high',     TRUE),
    ('OKTA', 'OKTA_SUPER_ADMIN',  'Super Administrator',     'Unrestricted tenant access',          'role',       'critical', TRUE),
    ('OKTA', 'OKTA_READONLY',     'Read Only Administrator', 'View configuration',                  'role',       'low',      FALSE),
    -- AD
    ('AD',   'AD_DOMAIN_ADMIN',   'Domain Admins',           'Full directory control',              'group',      'critical', TRUE),
    ('AD',   'AD_SERVER_OPS',     'Server Operators',        'Administer domain controllers',       'group',      'critical', TRUE),
    ('AD',   'AD_HELPDESK',       'Helpdesk Operators',      'Reset passwords, unlock accounts',    'group',      'medium',   FALSE),
    ('AD',   'AD_BACKUP_OPS',     'Backup Operators',        'Backup and restore files',            'group',      'high',     TRUE),
    -- Salesforce
    ('SALES','SF_SYS_ADMIN',      'System Administrator',    'Full org configuration',              'role',       'critical', TRUE),
    ('SALES','SF_SALES_USER',     'Sales User',              'Standard sales access',               'role',       'low',      FALSE),
    ('SALES','SF_REPORT_ADMIN',   'Report Administrator',    'Manage all reports & dashboards',     'role',       'medium',   FALSE),
    -- Workday
    ('WORK', 'WORK_HR_PARTNER',   'HR Business Partner',     'View and edit worker records',        'role',       'high',     FALSE),
    ('WORK', 'WORK_PAYROLL_ADMIN','Payroll Administrator',   'Run payroll, edit compensation',      'role',       'critical', TRUE),
    ('WORK', 'WORK_READONLY',     'Worker Read Only',        'View worker records',                 'role',       'low',      FALSE),
    -- GitHub
    ('GH',   'GH_ORG_OWNER',      'Organization Owner',      'Full org and repo control',           'role',       'critical', TRUE),
    ('GH',   'GH_REPO_ADMIN',     'Repository Admin',        'Administer repository settings',      'role',       'high',     TRUE),
    ('GH',   'GH_WRITE',          'Write',                   'Push to repositories',                'role',       'medium',   FALSE),
    ('GH',   'GH_SECRETS_ADMIN',  'Actions Secrets Admin',   'Manage CI secrets',                   'role',       'critical', TRUE),
    -- Jira
    ('JIRA', 'JIRA_SITE_ADMIN',   'Site Administrator',      'Full Jira/Confluence admin',          'role',       'high',     TRUE),
    ('JIRA', 'JIRA_PROJECT_ADMIN','Project Administrator',   'Administer projects',                 'role',       'medium',   FALSE),
    ('JIRA', 'JIRA_USER',         'Standard User',           'Standard issue access',               'role',       'low',      FALSE)
) AS v(system_code, code, name, description, etype, risk, priv)
JOIN system_app s ON s.code = v.system_code
ON CONFLICT (system_id, code) DO NOTHING;

-- =============================================================================
-- RISK RULES
-- =============================================================================
INSERT INTO risk_rule (code, name, description, category, severity, weight, logic_hint)
VALUES
    ('RR-SOD-001', 'Segregation of Duties Conflict',
     'An identity holds two entitlements that constitute a toxic combination.',
     'sod', 'critical', 1.50,
     'Join access_grant → sod_rule on (entitlement_a, entitlement_b) for the same identity.'),

    ('RR-DORM-001', 'Dormant Account',
     'An active account has not authenticated within the dormancy window.',
     'dormancy', 'medium', 1.00,
     'account.status = active AND (last_login_at IS NULL OR last_login_at < now() - IDRM_DORMANCY_DAYS).'),

    ('RR-DORM-002', 'Dormant Privileged Account',
     'A privileged account has not authenticated within the dormancy window.',
     'dormancy', 'high', 1.25,
     'As RR-DORM-001 but account_type = privileged.'),

    ('RR-ORPH-001', 'Orphaned Account',
     'An active account belongs to a terminated identity.',
     'orphan', 'critical', 1.50,
     'account.status = active AND identity.employment_status = terminated.'),

    ('RR-ORPH-002', 'No Manager Assigned',
     'An active employee identity has no manager recorded.',
     'orphan', 'low', 0.75,
     'identity.employment_status = active AND manager_id IS NULL AND identity_type = employee.'),

    ('RR-PRIV-001', 'Privileged Account Without MFA',
     'A privileged account does not have MFA enabled.',
     'mfa', 'critical', 1.50,
     'account.account_type = privileged AND mfa_enabled = false AND status = active.'),

    ('RR-PRIV-002', 'Standing Privileged Access',
     'A privileged grant has no expiry date.',
     'privilege', 'high', 1.25,
     'access_grant.state = active AND entitlement.is_privileged AND expires_at IS NULL.'),

    ('RR-PRIV-003', 'Excessive Privileged Entitlements',
     'An identity holds more than three privileged entitlements.',
     'privilege', 'high', 1.25,
     'COUNT(DISTINCT entitlement) per identity WHERE is_privileged GROUP BY identity HAVING COUNT > 3.'),

    ('RR-HYG-001',  'Stale Grant (Unused 90+ Days)',
     'An active grant has not been exercised in over 90 days.',
     'hygiene', 'medium', 1.00,
     'access_grant.state = active AND (last_used_at IS NULL OR last_used_at < now() - 90 days).'),

    ('RR-HYG-002',  'Password Never Rotated',
     'An active account password has not changed in over 365 days.',
     'hygiene', 'medium', 0.75,
     'account.status = active AND password_last_changed_at < now() - 365 days.'),

    ('RR-HYG-003',  'Shared Account In Use',
     'A shared account is active and holds entitlements.',
     'compliance', 'high', 1.25,
     'account.account_type = shared AND account.status = active.'),

    ('RR-COMP-001', 'Terminated Identity With Active Access',
     'A terminated identity still holds one or more active grants.',
     'compliance', 'critical', 1.50,
     'identity.employment_status = terminated AND EXISTS active access_grant.'),

    ('RR-PRIV-004', 'Emergency Account Active Outside Break-Glass',
     'An emergency account is enabled without an active break-glass ticket.',
     'privilege', 'high', 1.25,
     'account.account_type = emergency AND account.status = active.')
ON CONFLICT (code) DO NOTHING;

-- =============================================================================
-- SoD RULES  (toxic pairs)
-- =============================================================================
INSERT INTO sod_rule (system_id, entitlement_a_id, entitlement_b_id, description, severity)
SELECT s.id, ea.id, eb.id, v.descr, v.sev
FROM (VALUES
    ('SAP',  'SAP_AP_CLERK',      'SAP_AP_APPROVER',    'Create invoices AND approve payments — classic AP fraud vector', 'critical'),
    ('SAP',  'SAP_VENDOR_MASTER', 'SAP_AP_APPROVER',    'Maintain vendor master AND approve payments',                    'critical'),
    ('SAP',  'SAP_GL_POST',       'SAP_FI_ADMIN',       'Post GL entries AND administer finance config',                  'high'),
    ('AWS',  'AWS_POWERUSER',     'AWS_IAM_ADMIN',      'Broad resource control AND identity administration',             'critical'),
    ('AWS',  'AWS_S3_DELETE',     'AWS_BILLING',        'Destroy data AND alter billing — destructive + concealment',     'high'),
    ('OKTA', 'OKTA_USER_ADMIN',   'OKTA_APP_ADMIN',     'Manage users AND manage app assignments',                        'high'),
    ('OKTA', 'OKTA_SUPER_ADMIN',  'OKTA_READONLY',      'Redundant conflicting admin scopes',                             'medium'),
    ('AD',   'AD_DOMAIN_ADMIN',   'AD_BACKUP_OPS',      'Directory control AND backup/restore capability',                'critical'),
    ('SALES','SF_SYS_ADMIN',      'SF_REPORT_ADMIN',    'Configure org AND control all reporting',                        'medium'),
    ('WORK', 'WORK_HR_PARTNER',   'WORK_PAYROLL_ADMIN', 'Edit worker records AND run payroll',                            'critical'),
    ('GH',   'GH_ORG_OWNER',      'GH_SECRETS_ADMIN',   'Own the org AND control CI secrets',                             'critical'),
    ('GH',   'GH_REPO_ADMIN',     'GH_WRITE',           'Administer repos AND push code — weak change control',           'medium')
) AS v(sys, a, b, descr, sev)
JOIN system_app  s  ON s.code  = v.sys
JOIN entitlement ea ON ea.system_id = s.id AND ea.code = v.a
JOIN entitlement eb ON eb.system_id = s.id AND eb.code = v.b
ON CONFLICT (system_id, entitlement_a_id, entitlement_b_id) DO NOTHING;

COMMIT;
