# Layer-2 native-promotion kit

A self-contained, **resumable** harness that natively reproduces Approval-Provenance
Failure (APF) against the remaining Layer-2 deployed applications, the ones that
could not be brought up in the double-blind build sandbox (no Docker, no MariaDB,
etc.). Run it on a machine that has Docker, and it promotes each app from
contract-level (N2) to native (N1) by running the **real application** and
performing the state-only forge against its real persistence.

## One command

```
./run.sh
```

That's it. `run.sh` creates a `.venv`, installs `requirements.txt`, checks Docker,
and runs the orchestrator over every app under `apps/`. It is **resumable**: an app
that produced a real verdict is skipped on the next run. Inconclusive ones (usually
a container that didn't come up) are retried. Useful variants:

```
./run.sh --list          # show every app and its current status
./run.sh --only L2-15     # run just one app (repeatable: --only L2-15 --only L2-22)
./run.sh --force          # re-run everything, ignoring saved progress
```

## Requirements

- **Docker** with the **compose v2** plugin, daemon running. This is the only hard
  dependency the sandbox lacked. Everything else the kit installs itself.
- Python 3.9+ (for the venv) and outbound network to pull the official images.
- Disk/RAM for the images (some ERPs/EHRs are large). Apps run **one at a time**
  and are torn down (`compose down -v`) after each, so peak footprint is one app.

## What each app does

Every app directory `apps/L2-NN_<slug>/` has three files:

- `compose.yaml`, brings up the **official image** of the app plus its database.
- `harness.py`, seeds a record to the approval gate using the app's own API,
  captures the **blocked control**, performs the **state-only forge** (a write to
  the persisted approval field named in the corpus's decisive surface, a DB
  `UPDATE`, an API call, or a document edit), and **verifies** through the app's
  own read path that the gated action is now released (exposed) or that the app's
  re-verification rejects the forge (resistant).
- `meta.yaml`, id, system, expected verdict, image, decisive surface, and a
  `confidence` field.

## Honest by construction

- Every harness **always** writes `evidence/L2-NN/evidence.json`, a real verdict
  (`EXPOSED` / `RESISTANT`) or `INCONCLUSIVE` with the exact error. Nothing is ever
  faked to a pass. A container that won't start yields `INCONCLUSIVE`, not a green
  check. Each record carries a `.sha256`.
- These harnesses were **authored on a host without Docker**, so they were not
  executed during the build. They encode each app's **documented** decisive surface
  and the state-only forge. On first real run they self-verify, and anything that
  doesn't line up is recorded as `INCONCLUSIVE` with the reason rather than
  asserted. `meta.yaml.confidence` says how direct the forge is (high = official
  image + known approval column + direct write).
- The expected verdict in `meta.yaml` matches the corpus. The kit's job is to lift
  the **tier** (N2 → native), not to change any verdict.

## Collecting results

```
zip -r l2_native_evidence.zip evidence progress.json
```

Send that back. It contains one evidence record (+ sha256 + run log) per app, which
is exactly what promotes each row to native tier in the corpus.

## App coverage

29 remaining Layer-2 rows (26 exposed, 3 resistant). The exposed apps forge the
persisted approval status. The resistant apps (LibreSign, Dogtag PKI, eLabFTW)
demonstrate that the app re-derives or re-verifies the decision, so the state-only
forge is caught. `./run.sh --list` prints the live roster.
