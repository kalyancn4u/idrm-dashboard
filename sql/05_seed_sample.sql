-- =============================================================================
--  IDRM — 05_seed_sample.sql
--  Operational sample data for demos and tests.
--  Idempotent: YES (guarded by NOT EXISTS on natural keys).
--  NOTE: app_user.password_hash is a PLACEHOLDER.
--        Run `make passwords` (flask seed-users) afterwards to set real hashes.
-- =============================================================================

BEGIN;

-- =============================================================================
-- CONSOLE USERS
-- =============================================================================
INSERT INTO app_user (username, email, full_name, password_hash, role, is_active)
VALUES
    ('admin',   'admin@idrm.local',   'Ada Administrator', 'PLACEHOLDER', 'admin',   TRUE),
    ('auditor', 'auditor@idrm.local', 'Alfred Auditor',    'PLACEHOLDER', 'auditor', TRUE),
    ('analyst', 'analyst@idrm.local', 'Nia Analyst',       'PLACEHOLDER', 'analyst', TRUE),
    ('viewer',  'viewer@idrm.local',  'Vic Viewer',        'PLACEHOLDER', 'viewer',  TRUE)
ON CONFLICT (username) DO NOTHING;

-- =============================================================================
-- IDENTITIES
-- =============================================================================
INSERT INTO identity (external_ref, display_name, email, identity_type, department, job_title,
                      employment_status, join_date, termination_date, is_privileged)
VALUES
    ('E1001', 'Priya Raghavan',   'priya.raghavan@acme.example',  'employee',        'Finance',      'AP Manager',            'active',     '2019-03-11', NULL,         TRUE),
    ('E1002', 'Marcus Oyelaran',  'marcus.oyelaran@acme.example', 'employee',        'Finance',      'AP Clerk',              'active',     '2021-07-01', NULL,         FALSE),
    ('E1003', 'Helena Brandt',    'helena.brandt@acme.example',   'employee',        'Finance',      'Financial Controller',  'active',     '2017-01-09', NULL,         TRUE),
    ('E1004', 'Tomas Lindqvist',  'tomas.lindqvist@acme.example', 'employee',        'Engineering',  'Platform Lead',         'active',     '2020-02-17', NULL,         TRUE),
    ('E1005', 'Aisha Bello',      'aisha.bello@acme.example',     'employee',        'Engineering',  'SRE',                   'active',     '2022-05-30', NULL,         TRUE),
    ('E1006', 'Ravi Chandrasekar','ravi.chandrasekar@acme.example','employee',       'Engineering',  'Backend Engineer',      'active',     '2023-01-23', NULL,         FALSE),
    ('E1007', 'Sofia Marchetti',  'sofia.marchetti@acme.example', 'employee',        'People Ops',   'HR Business Partner',   'active',     '2018-11-05', NULL,         FALSE),
    ('E1008', 'Daniel Okonkwo',   'daniel.okonkwo@acme.example',  'employee',        'People Ops',   'Payroll Admin',         'active',     '2019-09-16', NULL,         TRUE),
    ('E1009', 'Yuki Tanaka',      'yuki.tanaka@acme.example',     'employee',        'RevOps',       'Salesforce Admin',      'active',     '2020-06-08', NULL,         TRUE),
    ('E1010', 'Grace Mwangi',     'grace.mwangi@acme.example',    'contractor',      'Engineering',  'Contract Developer',    'active',     '2024-02-01', NULL,         FALSE),
    ('E1011', 'Lars Petersen',    'lars.petersen@acme.example',   'employee',        'Engineering',  'Former DevOps Engineer','terminated', '2018-04-02', '2025-01-31', TRUE),
    ('E1012', 'Nadia Haddad',     'nadia.haddad@acme.example',    'employee',        'Finance',      'Former AP Clerk',       'terminated', '2020-10-12', '2024-11-15', FALSE),
    ('E1013', 'Vendor Integration Bot', NULL,                     'service_account', 'Engineering',  'CI/CD service identity','active',     '2023-03-01', NULL,         TRUE),
    ('E1014', 'Backup Automation',      NULL,                     'robot',           'Infra Ops',    'Scheduled backup job',  'active',     '2019-01-01', NULL,         TRUE),
    ('E1015', 'Acme Consulting LLP',    'contact@acmeconsult.example','vendor',     'External',     'Managed service vendor','active',    '2023-08-14', NULL,         FALSE),
    ('E1016', 'Elena Kovacs',     'elena.kovacs@acme.example',    'employee',        'Infra Ops',    'Windows Admin',         'active',     '2017-05-22', NULL,         TRUE),
    ('E1017', 'Omar Farouk',      'omar.farouk@acme.example',     'employee',        'Infra Ops',    'Backup Operator',       'active',     '2021-12-06', NULL,         TRUE),
    ('E1018', 'Chloe Dubois',     'chloe.dubois@acme.example',    'employee',        'DevEx',        'Developer Experience',  'active',     '2022-09-19', NULL,         FALSE)
ON CONFLICT (external_ref) DO NOTHING;

-- Assign managers (self-referencing FK)
UPDATE identity SET manager_id = (SELECT id FROM identity WHERE external_ref = 'E1003')
 WHERE external_ref IN ('E1001', 'E1002', 'E1012');
UPDATE identity SET manager_id = (SELECT id FROM identity WHERE external_ref = 'E1004')
 WHERE external_ref IN ('E1005', 'E1006', 'E1010', 'E1013');
UPDATE identity SET manager_id = (SELECT id FROM identity WHERE external_ref = 'E1016')
 WHERE external_ref IN ('E1017', 'E1014');
UPDATE identity SET manager_id = (SELECT id FROM identity WHERE external_ref = 'E1007')
 WHERE external_ref = 'E1008';
UPDATE identity SET manager_id = (SELECT id FROM identity WHERE external_ref = 'E1018')
 WHERE external_ref IN ('E1009', 'E1018');

-- =============================================================================
-- ACCOUNTS
-- =============================================================================
INSERT INTO account (identity_id, system_id, username, account_type, status,
                     mfa_enabled, last_login_at, password_last_changed_at)
SELECT i.id, s.id, v.username, v.atype, v.status, v.mfa, v.last_login, v.pwd_changed
FROM (VALUES
    ('E1001', 'SAP',   'p.raghavan',      'privileged', 'active',   TRUE,  now() - INTERVAL '2 days',   now() - INTERVAL '120 days'),
    ('E1001', 'WORK',  'praghavan',       'standard',   'active',   TRUE,  now() - INTERVAL '5 days',   now() - INTERVAL '200 days'),
    ('E1002', 'SAP',   'm.oyelaran',      'standard',   'active',   TRUE,  now() - INTERVAL '1 day',    now() - INTERVAL '60 days'),
    ('E1003', 'SAP',   'h.brandt',        'privileged', 'active',   TRUE,  now() - INTERVAL '1 day',    now() - INTERVAL '30 days'),
    ('E1003', 'WORK',  'hbrandt',         'standard',   'active',   TRUE,  now() - INTERVAL '12 days',  now() - INTERVAL '180 days'),
    ('E1004', 'AWS',   'tomas.l',         'privileged', 'active',   TRUE,  now() - INTERVAL '3 hours',  now() - INTERVAL '45 days'),
    ('E1004', 'GH',    'tlindqvist',      'privileged', 'active',   TRUE,  now() - INTERVAL '2 hours',  now() - INTERVAL '45 days'),
    ('E1005', 'AWS',   'aisha.b',         'privileged', 'active',   FALSE, now() - INTERVAL '6 hours',  now() - INTERVAL '20 days'),
    ('E1005', 'GH',    'abello',          'standard',   'active',   TRUE,  now() - INTERVAL '1 day',    now() - INTERVAL '20 days'),
    ('E1006', 'GH',    'rchandra',        'standard',   'active',   TRUE,  now() - INTERVAL '4 days',   now() - INTERVAL '90 days'),
    ('E1006', 'JIRA',  'rchandra',        'standard',   'active',   TRUE,  now() - INTERVAL '4 days',   now() - INTERVAL '90 days'),
    ('E1007', 'WORK',  's.marchetti',     'standard',   'active',   TRUE,  now() - INTERVAL '2 days',   now() - INTERVAL '150 days'),
    ('E1008', 'WORK',  'd.okonkwo',       'privileged', 'active',   TRUE,  now() - INTERVAL '1 day',    now() - INTERVAL '75 days'),
    ('E1009', 'SALES', 'y.tanaka',        'privileged', 'active',   TRUE,  now() - INTERVAL '3 days',   now() - INTERVAL '100 days'),
    ('E1009', 'OKTA',  'y.tanaka',        'privileged', 'active',   TRUE,  now() - INTERVAL '3 days',   now() - INTERVAL '100 days'),
    ('E1010','GH',     'gmwangi',         'standard',   'active',   TRUE,  now() - INTERVAL '10 days',  now() - INTERVAL '40 days'),
    ('E1011','AWS',    'l.petersen',      'privileged', 'active',   FALSE, now() - INTERVAL '210 days', now() - INTERVAL '400 days'),
    ('E1011','GH',     'lpetersen',       'privileged', 'active',   FALSE, now() - INTERVAL '205 days', now() - INTERVAL '400 days'),
    ('E1011','AD',     'l.petersen',      'privileged', 'active',   FALSE, now() - INTERVAL '215 days', now() - INTERVAL '410 days'),
    ('E1012','SAP',    'n.haddad',        'standard',   'active',   FALSE, now() - INTERVAL '160 days', now() - INTERVAL '380 days'),
    ('E1013','AWS',    'svc-ci-bot',      'service',    'active',   FALSE, now() - INTERVAL '5 minutes',now() - INTERVAL '10 days'),
    ('E1013','GH',     'svc-ci-bot',      'service',    'active',   FALSE, now() - INTERVAL '5 minutes',now() - INTERVAL '10 days'),
    ('E1014','AD',     'svc-backup',      'service',    'active',   FALSE, now() - INTERVAL '8 hours',  now() - INTERVAL '300 days'),
    ('E1015','SALES',  'acmeconsult',     'shared',     'active',   FALSE, now() - INTERVAL '20 days',  now() - INTERVAL '250 days'),
    ('E1016','AD',     'e.kovacs',        'privileged', 'active',   TRUE,  now() - INTERVAL '4 hours',  now() - INTERVAL '55 days'),
    ('E1016','OKTA',   'e.kovacs',        'privileged', 'active',   TRUE,  now() - INTERVAL '4 hours',  now() - INTERVAL '55 days'),
    ('E1017','AD',     'o.farouk',        'privileged', 'active',   TRUE,  now() - INTERVAL '2 days',   now() - INTERVAL '70 days'),
    ('E1018','GH',     'cdubois',         'standard',   'active',   TRUE,  now() - INTERVAL '1 day',    now() - INTERVAL '25 days'),
    ('E1018','JIRA',   'cdubois',         'standard',   'active',   TRUE,  now() - INTERVAL '1 day',    now() - INTERVAL '25 days')
) AS v(ref, sys, username, atype, status, mfa, last_login, pwd_changed)
JOIN identity   i ON i.external_ref = v.ref
JOIN system_app s ON s.code        = v.sys
ON CONFLICT (system_id, username) DO NOTHING;

-- =============================================================================
-- ACCESS GRANTS
-- =============================================================================
INSERT INTO access_grant (account_id, entitlement_id, granted_by, granted_at, expires_at,
                          last_used_at, state, justification)
SELECT a.id, e.id, v.granted_by, v.granted_at, v.expires_at, v.last_used, v.state, v.justif
FROM (VALUES
    -- Priya: AP Manager — has the classic AP clerk + approver combo (SoD risk)
    ('E1001','SAP','p.raghavan','SAP_AP_CLERK',      'hr-system',  now() - INTERVAL '700 days', NULL,                        now() - INTERVAL '3 days',  'active', 'Legacy access from previous role'),
    ('E1001','SAP','p.raghavan','SAP_AP_APPROVER',   'hr-system',  now() - INTERVAL '400 days', NULL,                        now() - INTERVAL '2 days',  'active', 'Approval authority for AP team'),
    ('E1001','SAP','p.raghavan','SAP_VENDOR_MASTER', 'cfo-office', now() - INTERVAL '380 days', NULL,                        now() - INTERVAL '30 days', 'active', 'Vendor onboarding ownership'),
    -- Marcus: AP Clerk only
    ('E1002','SAP','m.oyelaran','SAP_AP_CLERK',      'hr-system',  now() - INTERVAL '300 days', NULL,                        now() - INTERVAL '1 day',   'active', 'Role-based'),
    -- Helena: Controller
    ('E1003','SAP','h.brandt',  'SAP_GL_POST',       'cfo-office', now() - INTERVAL '900 days', NULL,                        now() - INTERVAL '4 days',  'active', 'Controller duties'),
    ('E1003','SAP','h.brandt',  'SAP_FI_ADMIN',      'cfo-office', now() - INTERVAL '200 days', now() + INTERVAL '60 days',  now() - INTERVAL '5 days',  'active', 'Temporary — FY close support'),
    -- Tomas: Platform Lead
    ('E1004','AWS','tomas.l',   'AWS_POWERUSER',     'iam-team',   now() - INTERVAL '500 days', NULL,                        now() - INTERVAL '3 hours', 'active', 'Platform engineering'),
    ('E1004','AWS','tomas.l',   'AWS_IAM_ADMIN',     'iam-team',   now() - INTERVAL '180 days', now() + INTERVAL '30 days',  now() - INTERVAL '1 day',   'active', 'Break-glass IAM authority'),
    ('E1004','GH', 'tlindqvist','GH_ORG_OWNER',      'devex',      now() - INTERVAL '600 days', NULL,                        now() - INTERVAL '2 hours', 'active', 'Org ownership'),
    -- Aisha: SRE, privileged without MFA, standing privilege
    ('E1005','AWS','aisha.b',   'AWS_POWERUSER',     'iam-team',   now() - INTERVAL '400 days', NULL,                        now() - INTERVAL '6 hours', 'active', 'SRE on-call'),
    ('E1005','AWS','aisha.b',   'AWS_IAM_ADMIN',     'iam-team',   now() - INTERVAL '400 days', NULL,                        now() - INTERVAL '7 days',  'active', 'Standing admin — no expiry'),
    ('E1005','GH', 'abello',    'GH_REPO_ADMIN',     'devex',      now() - INTERVAL '300 days', NULL,                        now() - INTERVAL '2 days',  'active', 'Repo administration'),
    -- Ravi: standard dev
    ('E1006','GH', 'rchandra',  'GH_WRITE',          'devex',      now() - INTERVAL '250 days', NULL,                        now() - INTERVAL '4 days',  'active', 'Development'),
    ('E1006','JIRA','rchandra', 'JIRA_USER',         'devex',      now() - INTERVAL '250 days', NULL,                        now() - INTERVAL '4 days',  'active', 'Standard access'),
    -- Sofia: HR
    ('E1007','WORK','s.marchetti','WORK_HR_PARTNER', 'people-ops', now() - INTERVAL '500 days', NULL,                        now() - INTERVAL '2 days',  'active', 'HRBP duties'),
    ('E1007','WORK','s.marchetti','WORK_READONLY',   'people-ops', now() - INTERVAL '500 days', NULL,                        now() - INTERVAL '2 days',  'active', 'Reporting'),
    -- Daniel: Payroll — HR partner + payroll = SoD
    ('E1008','WORK','d.okonkwo', 'WORK_PAYROLL_ADMIN','people-ops',now() - INTERVAL '450 days', NULL,                        now() - INTERVAL '1 day',   'active', 'Payroll operations'),
    ('E1008','WORK','d.okonkwo', 'WORK_HR_PARTNER',  'people-ops', now() - INTERVAL '200 days', NULL,                        now() - INTERVAL '10 days', 'active', 'Cross-trained during restructure'),
    -- Yuki: Salesforce + Okta admin
    ('E1009','SALES','y.tanaka', 'SF_SYS_ADMIN',     'revops',     now() - INTERVAL '600 days', NULL,                        now() - INTERVAL '3 days',  'active', 'Salesforce administration'),
    ('E1009','SALES','y.tanaka', 'SF_REPORT_ADMIN',  'revops',     now() - INTERVAL '600 days', NULL,                        now() - INTERVAL '3 days',  'active', 'Reporting ownership'),
    ('E1009','OKTA','y.tanaka',  'OKTA_USER_ADMIN',  'iam-team',   now() - INTERVAL '350 days', NULL,                        now() - INTERVAL '5 days',  'active', 'User lifecycle support'),
    ('E1009','OKTA','y.tanaka',  'OKTA_APP_ADMIN',   'iam-team',   now() - INTERVAL '350 days', NULL,                        now() - INTERVAL '5 days',  'active', 'App integration support'),
    -- Grace: contractor
    ('E1010','GH', 'gmwangi',    'GH_WRITE',         'devex',      now() - INTERVAL '120 days', now() + INTERVAL '120 days', now() - INTERVAL '10 days', 'active', 'Contract term'),
    -- Lars: TERMINATED but still holds active access (critical finding)
    ('E1011','AWS','l.petersen', 'AWS_POWERUSER',    'iam-team',   now() - INTERVAL '800 days', NULL,                        now() - INTERVAL '210 days','active', 'Not revoked on offboarding'),
    ('E1011','AWS','l.petersen', 'AWS_IAM_ADMIN',    'iam-team',   now() - INTERVAL '700 days', NULL,                        now() - INTERVAL '215 days','active', 'Not revoked on offboarding'),
    ('E1011','GH', 'lpetersen',  'GH_ORG_OWNER',     'devex',      now() - INTERVAL '800 days', NULL,                        now() - INTERVAL '205 days','active', 'Not revoked on offboarding'),
    ('E1011','AD', 'l.petersen', 'AD_DOMAIN_ADMIN',  'infra-ops',  now() - INTERVAL '900 days', NULL,                        now() - INTERVAL '220 days','active', 'Not revoked on offboarding'),
    -- Nadia: terminated AP clerk
    ('E1012','SAP','n.haddad',   'SAP_AP_CLERK',     'hr-system',  now() - INTERVAL '600 days', NULL,                        now() - INTERVAL '160 days','active', 'Not revoked on offboarding'),
    -- Service accounts
    ('E1013','AWS','svc-ci-bot', 'AWS_POWERUSER',    'terraform',  now() - INTERVAL '300 days', NULL,                        now() - INTERVAL '5 minutes','active','CI/CD pipeline'),
    ('E1013','GH', 'svc-ci-bot', 'GH_SECRETS_ADMIN', 'terraform',  now() - INTERVAL '300 days', NULL,                        now() - INTERVAL '5 minutes','active','CI/CD secrets'),
    ('E1014','AD', 'svc-backup', 'AD_BACKUP_OPS',    'infra-ops',  now() - INTERVAL '1000 days',NULL,                        now() - INTERVAL '8 hours', 'active','Scheduled backups'),
    -- Vendor shared account
    ('E1015','SALES','acmeconsult','SF_SALES_USER',  'revops',     now() - INTERVAL '180 days', now() + INTERVAL '30 days',  now() - INTERVAL '20 days', 'active','Vendor support access'),
    -- Elena: Windows Admin — SoD with backup
    ('E1016','AD', 'e.kovacs',   'AD_DOMAIN_ADMIN',  'infra-ops',  now() - INTERVAL '900 days', NULL,                        now() - INTERVAL '4 hours', 'active','Directory administration'),
    ('E1016','AD', 'e.kovacs',   'AD_SERVER_OPS',    'infra-ops',  now() - INTERVAL '900 days', NULL,                        now() - INTERVAL '4 hours', 'active','Server operations'),
    ('E1016','OKTA','e.kovacs',  'OKTA_SUPER_ADMIN', 'iam-team',   now() - INTERVAL '400 days', NULL,                        now() - INTERVAL '1 day',   'active','IdP administration'),
    ('E1016','OKTA','e.kovacs',  'OKTA_READONLY',    'iam-team',   now() - INTERVAL '400 days', NULL,                        now() - INTERVAL '1 day',   'active','Monitoring'),
    -- Omar: Backup operator — SoD with Elena
    ('E1017','AD', 'o.farouk',   'AD_BACKUP_OPS',    'infra-ops',  now() - INTERVAL '500 days', NULL,                        now() - INTERVAL '2 days',  'active','Backup operations'),
    ('E1017','AD', 'o.farouk',   'AD_HELPDESK',      'infra-ops',  now() - INTERVAL '500 days', NULL,                        now() - INTERVAL '2 days',  'active','Helpdesk rotation'),
    -- Chloe
    ('E1018','GH', 'cdubois',    'GH_WRITE',         'devex',      now() - INTERVAL '200 days', NULL,                        now() - INTERVAL '1 day',   'active','Development'),
    ('E1018','GH', 'cdubois',    'GH_REPO_ADMIN',    'devex',      now() - INTERVAL '200 days', NULL,                        now() - INTERVAL '1 day',   'active','Repo maintenance'),
    ('E1018','JIRA','cdubois',   'JIRA_PROJECT_ADMIN','devex',     now() - INTERVAL '200 days', NULL,                        now() - INTERVAL '1 day',   'active','Project administration')
) AS v(ref, sys, uname, ent_code, granted_by, granted_at, expires_at, last_used, state, justif)
JOIN identity    i ON i.external_ref = v.ref
JOIN system_app  s ON s.code         = v.sys
JOIN account     a ON a.system_id    = s.id AND a.username = v.uname
JOIN entitlement e ON e.system_id    = s.id AND e.code     = v.ent_code
ON CONFLICT (account_id, entitlement_id) DO NOTHING;

-- =============================================================================
-- FINDINGS  (hand-authored so severities line up with the seeded risk story)
-- =============================================================================
INSERT INTO finding (risk_rule_id, identity_id, account_id, access_grant_id, system_id,
                     title, description, severity, status, assigned_to, detected_at)
SELECT rr.id, i.id, a.id, g.id, s.id, v.title, v.descr, v.sev, v.status, u.id, v.detected
FROM (VALUES
    ('RR-COMP-001','E1011','AWS','l.petersen','AWS_POWERUSER',
     'Terminated identity retains AWS admin access',
     'Lars Petersen was terminated on 2025-01-31 but still holds PowerUser and IAM admin grants on AWS production.',
     'critical','open', 'admin', now() - INTERVAL '12 days'),

    ('RR-ORPH-001','E1011','GH','lpetersen','GH_ORG_OWNER',
     'Terminated identity retains GitHub org ownership',
     'Org owner privileges persist after offboarding — supply-chain risk.',
     'critical','in_review','admin', now() - INTERVAL '11 days'),

    ('RR-SOD-001','E1001','SAP','p.raghavan','SAP_AP_APPROVER',
     'Segregation of duties conflict: AP Clerk + AP Approver',
     'Priya Raghavan can both create vendor invoices and approve their payment — classic AP fraud vector.',
     'critical','open','analyst', now() - INTERVAL '9 days'),

    ('RR-SOD-001','E1008','WORK','d.okonkwo','WORK_HR_PARTNER',
     'Segregation of duties conflict: HR Partner + Payroll Admin',
     'Daniel Okonkwo can edit worker records and run payroll in the same system.',
     'critical','open','analyst', now() - INTERVAL '9 days'),

    ('RR-PRIV-001','E1005','AWS','aisha.b','AWS_IAM_ADMIN',
     'Privileged AWS account without MFA',
     'IAMFullAccess grant on an account with mfa_enabled = false.',
     'critical','open','admin', now() - INTERVAL '8 days'),

    ('RR-SOD-001','E1016','AD','e.kovacs','AD_BACKUP_OPS',
     'Segregation of duties conflict: Domain Admin + Backup Operator',
     'Combined directory control and restore capability defeats change-control.',
     'critical','in_review','analyst', now() - INTERVAL '8 days'),

    ('RR-PRIV-003','E1016',NULL,NULL,NULL,
     'Excessive privileged entitlements (5 held)',
     'Elena Kovacs holds five privileged entitlements across AD and Okta.',
     'high','open','admin', now() - INTERVAL '7 days'),

    ('RR-SOD-001','E1009','SALES','y.tanaka','SF_REPORT_ADMIN',
     'Segregation of duties conflict: System Admin + Report Admin',
     'Yuki Tanaka controls both org configuration and all reporting.',
     'high','open','analyst', now() - INTERVAL '7 days'),

    ('RR-DORM-002','E1011','AD','l.petersen','AD_DOMAIN_ADMIN',
     'Dormant privileged account (220 days)',
     'Domain Admin account has not authenticated in 220 days.',
     'high','open','admin', now() - INTERVAL '6 days'),

    ('RR-PRIV-002','E1004','AWS','tomas.l','AWS_IAM_ADMIN',
     'Standing privileged access without expiry',
     'IAM admin grant has no expiry date — convert to just-in-time.',
     'high','open','admin', now() - INTERVAL '6 days'),

    ('RR-HYG-003','E1015','SALES','acmeconsult','SF_SALES_USER',
     'Shared vendor account with active entitlements',
     'Shared credentials prevent individual attribution.',
     'high','accepted_risk','admin', now() - INTERVAL '20 days'),

    ('RR-HYG-001','E1001','SAP','p.raghavan','SAP_VENDOR_MASTER',
     'Vendor master grant unused for 30+ days',
     'Grant has not been exercised in the observation window.',
     'medium','open','analyst', now() - INTERVAL '5 days'),

    ('RR-DORM-001','E1012','SAP','n.haddad','SAP_AP_CLERK',
     'Dormant account (160 days) on terminated identity',
     'Former AP clerk account remains enabled.',
     'medium','open','admin', now() - INTERVAL '5 days'),

    ('RR-HYG-002','E1011','AWS','l.petersen','AWS_POWERUSER',
     'Password not rotated in 400+ days',
     'Password age exceeds the 365-day control.',
     'medium','open','admin', now() - INTERVAL '4 days'),

    ('RR-PRIV-002','E1013','GH','svc-ci-bot','GH_SECRETS_ADMIN',
     'Service account holds standing secrets-admin rights',
     'CI bot can read and rotate all Actions secrets.',
     'high','in_review','admin', now() - INTERVAL '4 days'),

    ('RR-ORPH-002','E1010',NULL,NULL,NULL,
     'Contractor identity has no manager assigned',
     'Grace Mwangi is an active contractor with no recorded manager.',
     'low','open',NULL, now() - INTERVAL '3 days'),

    ('RR-HYG-001','E1017','AD','o.farouk','AD_HELPDESK',
     'Helpdesk grant unused for 100+ days',
     'Grant appears stale; review for removal.',
     'low','false_positive','analyst', now() - INTERVAL '15 days'),

    ('RR-PRIV-004','E1014','AD','svc-backup','AD_BACKUP_OPS',
     'Emergency/service account active outside break-glass',
     'Service backup account is permanently enabled.',
     'high','remediated','admin', now() - INTERVAL '25 days')
) AS v(rule_code, ref, sys, uname, ent_code, title, descr, sev, status, assignee, detected)
JOIN risk_rule rr ON rr.code = v.rule_code
JOIN identity  i  ON i.external_ref = v.ref
LEFT JOIN system_app s ON s.code = v.sys
LEFT JOIN account    a ON a.system_id = s.id AND a.username = v.uname
LEFT JOIN entitlement e ON e.system_id = s.id AND e.code    = v.ent_code
LEFT JOIN access_grant g ON g.account_id = a.id AND g.entitlement_id = e.id
LEFT JOIN app_user   u ON u.username = v.assignee
WHERE NOT EXISTS (SELECT 1 FROM finding f WHERE f.title = v.title);

-- Mark remediated finding as actually remediated
UPDATE finding
   SET remediated_at = now() - INTERVAL '24 days',
       remediated_by = (SELECT id FROM app_user WHERE username = 'admin'),
       remediation_note = 'Service account disabled; replaced with short-lived credential issued by the backup orchestrator.'
 WHERE status = 'remediated' AND remediated_at IS NULL;

-- =============================================================================
-- EVIDENCE
-- =============================================================================
INSERT INTO evidence (finding_id, kind, title, uri, content, collected_by)
SELECT f.id, v.kind, v.title, v.uri, v.content, u.id
FROM (VALUES
    ('Terminated identity retains AWS admin access','note',
     'Offboarding ticket reference',
     NULL,
     'HR termination ticket HR-2025-0431 confirms last working day 2025-01-31. No deprovisioning ticket raised.',
     'auditor'),
    ('Terminated identity retains AWS admin access','query',
     'Evidence query — active grants for terminated identities',
     'sql/evidence/q_terminated_active_grants.sql',
     'SELECT i.external_ref, i.display_name, s.code, e.code FROM identity i JOIN account a ON a.identity_id=i.id JOIN access_grant g ON g.account_id=a.id JOIN entitlement e ON e.id=g.entitlement_id JOIN system_app s ON s.id=a.system_id WHERE i.employment_status=''terminated'' AND g.state=''active'';',
     'auditor'),
    ('Segregation of duties conflict: AP Clerk + AP Approver','note',
     'SoD matrix extract',
     NULL,
     'SoD matrix row SOD-SAP-001 flags AP_CLERK × AP_APPROVER as critical.',
     'auditor'),
    ('Privileged AWS account without MFA','link',
     'AWS IAM credential report (redacted)',
     'https://console.aws.amazon.com/iam/home#/credential_report',
     'credential report shows password_enabled=true, mfa_active=false for user aisha.b',
     'admin'),
    ('Shared vendor account with active entitlements','note',
     'Risk acceptance record',
     NULL,
     'Risk accepted by CISO on 2025-01-15 until the vendor portal migration completes (target Q3).',
     'admin')
) AS v(finding_title, kind, title, uri, content, collector)
JOIN finding  f ON f.title = v.finding_title
LEFT JOIN app_user u ON u.username = v.collector
WHERE NOT EXISTS (SELECT 1 FROM evidence ev WHERE ev.title = v.title AND ev.finding_id = f.id);

-- =============================================================================
-- REVIEW CAMPAIGN
-- =============================================================================
INSERT INTO review_campaign (code, name, description, scope_system_id, status, starts_at, due_at, created_by)
SELECT 'RC-2025-Q1-AP',
       'Q1 2025 — Finance Access Certification',
       'Quarterly certification of all SAP finance entitlements following the AP segregation review.',
       s.id, 'active', now() - INTERVAL '14 days', now() + INTERVAL '14 days',
       (SELECT id FROM app_user WHERE username = 'admin')
FROM system_app s WHERE s.code = 'SAP'
ON CONFLICT (code) DO NOTHING;

INSERT INTO review_campaign (code, name, description, scope_system_id, status, starts_at, due_at, completed_at, created_by)
SELECT 'RC-2024-Q4-INFRA',
       'Q4 2024 — Infrastructure Privileged Access Review',
       'Completed certification of AD, AWS and Okta privileged access.',
       NULL, 'completed', now() - INTERVAL '120 days', now() - INTERVAL '90 days',
       now() - INTERVAL '88 days',
       (SELECT id FROM app_user WHERE username = 'admin')
ON CONFLICT (code) DO NOTHING;

-- Populate review items for the active campaign
INSERT INTO review_item (campaign_id, access_grant_id, reviewer_id, decision, decision_note, decided_at)
SELECT c.id, g.id,
       (SELECT id FROM app_user WHERE username = 'admin'),
       CASE WHEN random() < 0.55 THEN 'pending'
            WHEN random() < 0.75 THEN 'approve'
            ELSE 'revoke' END,
       NULL, NULL
FROM review_campaign c
JOIN access_grant g ON TRUE
JOIN account      a ON a.id = g.account_id
JOIN system_app   s ON s.id = a.system_id
WHERE c.code = 'RC-2025-Q1-AP'
  AND s.code = 'SAP'
  AND g.state = 'active'
ON CONFLICT (campaign_id, access_grant_id) DO NOTHING;

-- Resolve decided items
UPDATE review_item ri
   SET decided_at = now() - (random() * INTERVAL '10 days'),
       decision_note = CASE ri.decision
           WHEN 'approve' THEN 'Business justification confirmed by system owner.'
           WHEN 'revoke'  THEN 'No longer required — role change effective last quarter.'
           ELSE NULL END
 WHERE ri.decision <> 'pending'
   AND ri.decided_at IS NULL;

-- =============================================================================
-- SCAN RUN HISTORY
-- =============================================================================
INSERT INTO scan_run (started_at, finished_at, triggered_by, trigger_source,
                      rules_evaluated, findings_created, findings_closed, status)
SELECT now() - (n || ' days')::INTERVAL,
       now() - (n || ' days')::INTERVAL + INTERVAL '42 seconds',
       (SELECT id FROM app_user WHERE username = 'admin'),
       CASE WHEN n % 3 = 0 THEN 'scheduled' ELSE 'manual' END,
       13, (random() * 5)::INT, (random() * 3)::INT, 'success'
FROM generate_series(1, 10) AS n
WHERE NOT EXISTS (SELECT 1 FROM scan_run);

-- =============================================================================
-- RECOMPUTE RISK SCORES
-- =============================================================================
SELECT fn_recompute_all_risk_scores();

COMMIT;
