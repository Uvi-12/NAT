# APF native reproduction, L2-22 OpenEMR (healthcare / EHR)

Native-tier (N1) result captured from a real run of the deployed application. The
harness that produced it is the single source of record in the in-tree kit at
`../l2-native-kit/apps/L2-22_openemr/`. Reproduce with:

    cd ../l2-native-kit && ./run.sh --only L2-22

- **Verdict:** EXPOSED.
- **Decisive surface:** billing.authorized.
- **Captured run (`evidence.json`):** seeded a billing line authorized=0, state-only UPDATE billing SET authorized=1, re-read confirms authorized=1 (authorize ACL bypassed).

This directory holds the captured, sanitized evidence of record. The runnable
compose + harness live once, in the kit, to avoid duplication.
