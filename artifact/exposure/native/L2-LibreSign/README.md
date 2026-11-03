# APF native reproduction, L2-08 LibreSign (Nextcloud e-signature)

Native-tier (N1) result captured from a real run of the deployed application. The
harness that produced it is the single source of record in the in-tree kit at
`../l2-native-kit/apps/L2-08_libresign/`. Reproduce with:

    cd ../l2-native-kit && ./run.sh --only L2-08

- **Verdict:** RESISTANT.
- **Decisive surface:** PAdES signatures re-parsed from the PDF.
- **Captured run (`evidence.json`):** state-only UPDATE oc_libresign_sign_request SET signed=now(), LibreSign re-derives the signature from the PDF and the forged status does NOT validate.

This directory holds the captured, sanitized evidence of record. The runnable
compose + harness live once, in the kit, to avoid duplication.
