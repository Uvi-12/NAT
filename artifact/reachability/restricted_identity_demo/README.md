# Restricted-identity end-to-end demonstration of APF

This is the controlled, fully offline counterpart to the native product
reproductions. It answers the sharpest reviewer question directly: can a
**restricted operational identity**, one that cannot approve, cannot read
application secrets, and cannot execute the protected action, nevertheless induce
the workflow to execute that action by writing the approval state, and does a
provenance-bound gate stop it.

The privilege separation here is **enforced by PostgreSQL**, not asserted in prose.
The `operator` role is the state-writer adversary. The database itself denies it the
secrets table and the protected-action table. Everything runs on a throwaway local
cluster and nothing leaves the machine.

## Run it

```
./run.sh
```

Needs a PostgreSQL install (`initdb`, `pg_ctl`, `psql`) and a non-root user.
`run.sh` creates a temporary cluster, runs `demo.sql`, checks the outcome, and tears
everything down. Exit code 0 means PASS. `expected_output.txt` is the committed
transcript so the result is checkable without running.

## Roles and the three capabilities the adversary lacks

| Role | Capability |
| --- | --- |
| `operator` | may `INSERT`/`UPDATE` the `approvals` table, and nothing else |
| `approval_svc` | the trusted approval service, holds the signing key |
| `wsvc` | the workflow service, reads approvals and secrets, performs the action |

The database `GRANT`s give `operator` no access to `secrets` (application secrets),
no access to `released_actions` (the protected effect), and no signing key. This is
exactly the paper's restricted state-writer adversary.

## What the run shows

**Part 1, vulnerable workflow.** Two negative controls first: `operator` is denied
when it reads `secrets` and denied when it tries to write `released_actions`
directly. So it cannot approve, cannot read secrets, and cannot execute the action.
It then writes one approval-shaped row (`status = approved`) for an action no human
approved. The workflow service resumes, trusts the row, and releases the protected
action. `RESULT-1 = 1`. The restricted identity caused the protected effect it could
not perform itself.

**Part 2, hardened workflow.** The trusted approval service issues a genuine approval
for a different action, carrying a provenance token, an HMAC over the action and
decision under a key the `operator` does not hold. The `operator` again forges
`status = approved` for its own action, but cannot mint a matching token. The
hardened workflow releases only rows whose token verifies under the key.
`RESULT-2a = 1` (genuine released), `RESULT-2b = 0` (forge rejected). The decisive
change is not more validation of the same mutable state. It is binding the decision
to an authority the state writer cannot reproduce, which is the paper's remedy.

## Scope

This is a reference model, not a product. It isolates the mechanism so the privilege
boundary is enforced and the result reproduces anywhere PostgreSQL runs. The native
product reproductions in `../../exposure/native/` show the same acceptance in real
application runtimes, and `../reachability.csv` shows that a non-approval principal
reaches the decisive field in each product's default deployment.
