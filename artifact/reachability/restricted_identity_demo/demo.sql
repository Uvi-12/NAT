-- End-to-end restricted-identity demonstration of APF, with the privilege
-- separation ENFORCED BY THE DATABASE (not asserted in prose). One key is used,
-- :key, passed by run.sh. The operator never receives it.
--
-- Roles:
--   operator      the state-writer adversary. May write the approval state, nothing else.
--   approval_svc  the trusted approval service. Issues genuine approvals (holds the key).
--   wsvc          the workflow service. Reads approvals and secrets, performs the action.

\set ON_ERROR_STOP off
\pset tuples_only on
\pset format unaligned

CREATE EXTENSION IF NOT EXISTS pgcrypto;

DROP TABLE IF EXISTS approvals, secrets, released_actions, hardened_released CASCADE;
DROP ROLE IF EXISTS operator, wsvc, approval_svc;
CREATE ROLE operator LOGIN;
CREATE ROLE wsvc LOGIN;
CREATE ROLE approval_svc LOGIN;

CREATE TABLE approvals (
  id serial PRIMARY KEY, action text NOT NULL,
  status text NOT NULL DEFAULT 'pending',   -- the decisive approval field
  approver text, token text);
CREATE TABLE secrets (name text PRIMARY KEY, value text NOT NULL);
CREATE TABLE released_actions  (id serial PRIMARY KEY, action text NOT NULL,
  released_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE hardened_released (id serial PRIMARY KEY, action text NOT NULL);
INSERT INTO secrets VALUES ('protected_tool_key','sk-REAL-PROTECTED-SECRET');

-- operator: may write the approval state, and nothing else
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM operator;
GRANT SELECT, INSERT, UPDATE ON approvals TO operator;
GRANT USAGE, SELECT ON SEQUENCE approvals_id_seq TO operator;
-- deliberately NOT granted to operator: secrets, released_actions, hardened_released

GRANT SELECT, INSERT, UPDATE ON approvals TO approval_svc;
GRANT USAGE, SELECT ON SEQUENCE approvals_id_seq TO approval_svc;

GRANT SELECT ON approvals TO wsvc;
GRANT SELECT ON secrets TO wsvc;
GRANT SELECT, INSERT ON released_actions  TO wsvc;
GRANT SELECT, INSERT ON hardened_released TO wsvc;
GRANT USAGE, SELECT ON SEQUENCE released_actions_id_seq  TO wsvc;
GRANT USAGE, SELECT ON SEQUENCE hardened_released_id_seq TO wsvc;

\echo '== PART 1: VULNERABLE (APF) WORKFLOW =='

\echo '-- [control 1] operator reads secrets (must be DENIED):'
SET ROLE operator;
SELECT value FROM secrets;
RESET ROLE;

\echo '-- [control 2] operator executes the protected action directly (must be DENIED):'
SET ROLE operator;
INSERT INTO released_actions(action) VALUES ('wire_transfer_50000');
RESET ROLE;

\echo '-- [forge] operator writes an approval-shaped row for an UNAPPROVED action:'
SET ROLE operator;
INSERT INTO approvals(action,status,approver)
  VALUES ('wire_transfer_50000','approved','ceo@example.com');
RESET ROLE;

\echo '-- [workflow] wsvc resumes and releases every action whose status = approved:'
SET ROLE wsvc;
INSERT INTO released_actions(action)
  SELECT action FROM approvals a
  WHERE a.status='approved'
    AND NOT EXISTS (SELECT 1 FROM released_actions r WHERE r.action=a.action);
RESET ROLE;

\echo '-- [RESULT-1] protected action released without human approval (expect 1):'
SELECT count(*) FROM released_actions WHERE action='wire_transfer_50000';

\echo '== PART 2: HARDENED (PROVENANCE-BOUND) WORKFLOW =='

\echo '-- [approval_svc] issues a GENUINE approval for refund_20 with a provenance token:'
SET ROLE approval_svc;
INSERT INTO approvals(action,status,approver,token)
  VALUES ('refund_20','approved','reviewer@example.com',
          encode(hmac('refund_20:approved', :'key', 'sha256'),'hex'));
RESET ROLE;

\echo '-- [forge] operator sets status=approved for wire_transfer_99999 (no key, no valid token):'
SET ROLE operator;
INSERT INTO approvals(action,status,approver)
  VALUES ('wire_transfer_99999','approved','ceo@example.com');
RESET ROLE;

\echo '-- [hardened workflow] wsvc releases ONLY rows whose token verifies under the key:'
SET ROLE wsvc;
INSERT INTO hardened_released(action)
  SELECT action FROM approvals a
  WHERE a.status='approved'
    AND a.token = encode(hmac(a.action||':'||a.status, :'key', 'sha256'),'hex')
    AND NOT EXISTS (SELECT 1 FROM hardened_released h WHERE h.action=a.action);
RESET ROLE;

\echo '-- [RESULT-2a] genuine refund_20 released (expect 1):'
SELECT count(*) FROM hardened_released WHERE action='refund_20';
\echo '-- [RESULT-2b] forged wire_transfer_99999 released (expect 0, forge rejected):'
SELECT count(*) FROM hardened_released WHERE action='wire_transfer_99999';
