# APF native reproduction, L2-15 Odoo Community (ERP / procurement)

Native-tier (N1) result captured from a real run of the deployed application. The
harness that produced it is the single source of record in the in-tree kit at
`../l2-native-kit/apps/L2-15_odoo/`. Reproduce with:

    cd ../l2-native-kit && ./run.sh --only L2-15

- **Verdict:** EXPOSED.
- **Decisive surface:** purchase.order.state == 'purchase'.
- **Captured run (`evidence.json`):** seeded a draft PO via XML-RPC, control state draft, state-only UPDATE purchase_order SET state='purchase', Odoo's own API then reports it committed (button_confirm bypassed).

This directory holds the captured, sanitized evidence of record. The runnable
compose + harness live once, in the kit, to avoid duplication.
