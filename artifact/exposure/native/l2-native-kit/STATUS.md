# Native-kit status and bring-up requirements

The kit is honest by construction. An application that does not come up cleanly is
recorded `INCONCLUSIVE` with its captured error, never a false pass. This file records
which applications produced a native verdict, what each remaining application needs to
reach one, and how to run a single application.

## Verdicts obtained with the shipped composes

Three of the 29 applications produced a native verdict directly from the original
composes:

| id | app | verdict |
| --- | --- | --- |
| L2-15 | Odoo Community 17 | EXPOSED |
| L2-22 | OpenEMR 7.0.2 | EXPOSED |
| L2-08 | LibreSign (Nextcloud 28) | RESISTANT |

Two more are fixed and expected to reach a verdict on re-run: Documenso (L2-06), whose
seed now supplies `DocumentData.id` (a Prisma `cuid()` with no database default), and
DocuSeal (L2-07), whose seed now sets `accounts.timezone` and `locale` (NOT NULL, no
default). Applications not run natively are source-verified: the consume path is traced
in source to the persisted field that releases the effect, with file and line recorded
in the evidence folder.

## Running one application

```
docker compose -f apps/L2-XX_<name>/compose.yaml up -d
docker compose -f apps/L2-XX_<name>/compose.yaml logs --no-color | tail -50
docker compose -f apps/L2-XX_<name>/compose.yaml down -v
```

The evidence file records the exact error for any `INCONCLUSIVE` application. The Docker
log above identifies a bring-up failure.

## Architecture note

The composes are the known-good originals. Do not add a global `platform: linux/amd64`
pin: forcing amd64 on a multi-arch image (Odoo, OpenEMR, Nextcloud) makes it run under
emulation on Apple Silicon and fail to start unless Rosetta emulation is enabled. If a
single application reports "no matching manifest for linux/arm64", its image is
amd64-only, run just that application with `DOCKER_DEFAULT_PLATFORM=linux/amd64
./run.sh --only L2-XX` and Rosetta enabled in Docker Desktop.

## Bring-up requirements for the remaining applications

- Reach a verdict once started (image is real): L2-06 Documenso, L2-07 DocuSeal,
  L2-09 Mayan EDMS, L2-29 eLabFTW.
- Container starts, but the decisive row needs the approval workflow configured first:
  L2-14 LedgerSMB (company plus an unapproved transaction), L2-24 EJBCA (CA, approval
  profile, pending request), L2-17 Apache Fineract (loan in approved-pending),
  L2-25 OpenBao (requires an OSS build that exposes control-groups).
- Needs extra services or a built instance image, left source-verified until the stack
  is completed: L2-10 OpenSign and L2-21 OpenHIM (MongoDB), L2-13 ERPNext (full Frappe
  bench), L2-18 care, L2-20 OpenELIS, L2-28 Dataverse, L2-02 Spinnaker, L2-23 Dogtag,
  L2-19 DHIS2 (slow boot, raise the readiness timeout), L2-01 Argo (needs Kubernetes).
- Image reference needs correcting or a source build: L2-30 Galaxy (a model/ORM-tier
  native run ships in `artifact/exposure/native/L2-Galaxy/`), L2-03 Consul Democracy,
  L2-04 Decidim, L2-05 Your Priorities, L2-31 InvenioRDM, L2-32 OSF, L2-33 Grafeas.

## Native coverage

Most remaining applications require their approval workflow configured, extra services,
or a built image, which is per-application work rather than a re-run. The native set
reported in the paper spans domains: Odoo, Dolibarr, Tryton, OpenEMR, and Galaxy among
the exposed cases, with the resistant controls LibreSign, TUF, in-toto, step-ca, and
one cosign run covering both Sigstore rows. The remaining applications are
source-verified, with this kit available to extend the native set.
