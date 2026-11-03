# Native-kit status, fixes, and how to diagnose a failing app

The kit is **honest by construction**: an app that does not come up cleanly is
recorded `INCONCLUSIVE`, never a false pass.

## Known-good baseline (first real run, Apple-Silicon Mac)

3 of 29 produced a real verdict with the **original** composes:

| id | app | verdict |
| --- | --- | --- |
| L2-15 | Odoo Community 17 | **EXPOSED** |
| L2-22 | OpenEMR 7.0.2 | **EXPOSED** |
| L2-08 | LibreSign (Nextcloud 28) | **RESISTANT** |

## What changed in this version (and what was reverted)

- **Reverted:** the `platform: linux/amd64` pins that an earlier patch baked into
  every compose. Forcing amd64 on a **multi-arch** image (Odoo, OpenEMR, Nextcloud)
  makes it run under emulation on Apple Silicon and **fails to start** unless Docker
  Desktop's Rosetta/amd64 emulation is on, which regressed the 3 apps above. The
  composes here are back to the known-good originals.
- **Kept, Documenso (L2-06):** seed now supplies `DocumentData.id` (a Prisma
  `cuid()` with no DB default). This is the only thing that stopped it. Expected
  **EXPOSED** on re-run.
- **Kept, DocuSeal (L2-07):** seed now sets `accounts.timezone`/`locale` (NOT NULL,
  no default). Expected **EXPOSED** on re-run.

## If an app fails with "no matching manifest for linux/arm64"

That app's image is amd64-only. Do **not** set the platform globally (it breaks the
multi-arch apps). Re-run just that app with the env var:

```
DOCKER_DEFAULT_PLATFORM=linux/amd64 ./run.sh --only L2-XX
```

Enable Rosetta in Docker Desktop (Settings → General → "Use Rosetta for x86/amd64
emulation") first, or the emulated container still won't start.

## How to diagnose any INCONCLUSIVE app (send me this)

The evidence file records the exact error, but for a bring-up failure the Docker log
is what I need. For one app:

```
docker compose -f apps/L2-XX_<name>/compose.yaml up -d
docker compose -f apps/L2-XX_<name>/compose.yaml logs --no-color | tail -50
docker compose -f apps/L2-XX_<name>/compose.yaml down -v
```

Paste that `logs` output (or zip the new `evidence/` folder). With the real error I
can fix the specific cause instead of guessing.

## Honest triage of the remaining apps

**Should reach a verdict once started (image is real. Fixed or fine):** L2-06
Documenso (fixed), L2-07 DocuSeal (fixed), L2-09 Mayan, L2-29 eLabFTW.

**Container starts but the decisive row needs the app's approval workflow set up
first (not just a re-run):** L2-14 LedgerSMB (company + un-approved txn), L2-24 EJBCA
(CA + approval profile + pending request), L2-17 Fineract (loan in approved-pending),
L2-25 OpenBao (confirm the OSS build exposes control-groups).

**Needs extra services or a built instance image (stays INCONCLUSIVE until the stack
is completed, honest to leave contract-level):** L2-10 OpenSign & L2-21 OpenHIM
(MongoDB), L2-13 ERPNext (full Frappe bench), L2-18 care, L2-20 OpenELIS, L2-28
Dataverse, L2-02 Spinnaker, L2-23 Dogtag, L2-19 DHIS2 (very slow boot, raise the
readiness timeout), L2-01 Argo (needs Kubernetes).

**Image reference needs correcting (build from source):** L2-30 Galaxy
(`galaxy/galaxy:23.1` is not published. A model/ORM-tier native run already ships in
`artifact/exposure/native/L2-Galaxy/`), L2-03 Consul Democracy, L2-04 Decidim, L2-05
Your Priorities (confirm image name), L2-31 InvenioRDM, L2-32 OSF, L2-33 Grafeas.

## Realistic native target

One `./run.sh` will not yield 20–25 native verdicts: most remaining apps need their
approval workflow configured, extra services, or a built image, per-app work, not a
re-run. A defensible native set spans domains: Odoo, Dolibarr, Tryton, OpenEMR,
Documenso, DocuSeal, Galaxy, plus the resistant controls (LibreSign, TUF, in-toto,
step-ca), with contract-level harnesses and this kit covering the rest.
