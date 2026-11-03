# APF native reproduction, Tryton ERP (purchase requisition)

Native-tier (N1) reproduction against the real `trytond` server and the
`purchase_requisition` module.

- **System / layer:** L2-16 (ERP / procurement), deployed-application corpus.
- **Pinned version:** `trytond 8.2.1`, `trytond_purchase_requisition 8.2.0`
  (+ the purchase/account/party/product/company/currency module chain at 8.2.x) , 
  replaces the earlier "repo revision at assessment" pin.
- **Dependencies:** `pip install trytond trytond_purchase_requisition
  trytond_purchase trytond_purchase_request trytond_company trytond_currency
  trytond_product trytond_party`. No network, no server process. A throwaway
  SQLite database is created and activated by `run.sh`.
- **Run:** `bash run.sh`
- **Decisive surface:** the persisted `state` field of `purchase.requisition`
  (draft → waiting → approved → processing). The authorized `approve` action is a
  group-guarded `@ModelView.button` that records `approved_by`. The processing
  path acts on requisitions in state `approved`.
- **What it shows:** with the requisition in `waiting` the processing path is
  blocked. The genuine `approve()` button records the approver and enforces the
  group. A **state-only** write of `state := 'approved'` (not through the button)
  is trusted by the processing path and releases the gated effect while leaving
  `approved_by` empty, unauthorized execution and false evidence of oversight.
- **Verdict:** EXPOSED (native). Confirms the corpus verdict at native tier.

Framework-requiring native PoC, not a gated crypto-only claim.
