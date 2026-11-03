# APF native reproduction, Dolibarr ERP (supplier-order approval)

Native-tier (N1) reproduction against the **real Dolibarr 19.0.4 runtime** and its
own `CommandeFournisseur` class, not a reconstruction. It promotes the Layer-2
Dolibarr row (L2-12) from N2 (documented contract) to native.

- **System / version:** Dolibarr ERP/CRM **19.0.4** (git tag `19.0`).
- **Dependencies:** PHP 8.x (`pdo_pgsql`), PostgreSQL, a Dolibarr instance with the
  Supplier module active. `apf_dolibarr.php` boots Dolibarr's real `master.inc.php`
  and drives its real classes. It is not standalone.
- **Decisive surface:** `llx_commande_fournisseur.fk_statut` (and `fk_user_approve`) , 
  the persisted supplier-order approval state. Approval is `STATUS_VALIDATED (1)` →
  `STATUS_ACCEPTED (2)`.
- **Mechanism:** ALS (approval-lifecycle status in a writable relational row).

## What it shows (captured in `run_output.txt`)

Using Dolibarr's real runtime and ORM:

1. A supplier order is created and legitimately **validated** via the real
   `valid($user)` path → `fk_statut = 1` (validated, **not** approved).
2. **Control:** at status 1 the order is not approved (`fk_user_approve = 0`). The
   authorised approval path is `approve($user)`, which requires the
   `fournisseur->commande->approuver` right and moves 1 → 2.
3. **Forge (state-only):** a single direct write , 
   `UPDATE llx_commande_fournisseur SET fk_statut = 2, fk_user_approve = 99999`, with
   **no** `approve()` call, **no** approver right, and a **non-existent** approver id.
4. **Resume:** the real `CommandeFournisseur::fetch()` reads the row back and reports
   the order **Approved (status 2)** by approver `99999`. The downstream
   `commande()` (order-sent) action then proceeds to `STATUS_ORDERSENT (3)`.

Verdict: **EXPOSED**, the resume/downstream logic trusts the persisted `fk_statut`
as proof that the approval authority acted. A state-writer who can write that row
forges the approval and defeats the gate without approving, without the right, and
under a forged approver identity. This is the Layer-2 deployed-application instance
of the same approval-provenance failure measured across the substrates.

## How to reproduce natively

1. Install Dolibarr 19.0.4 against PostgreSQL (standard installer), activate the
   Supplier module.
2. Point the harness at the instance's `htdocs` and run it with the instance's PHP:
   `DOLI_HT=/path/to/dolibarr/htdocs php apf_dolibarr.php`
3. Observe the sequence in `run_output.txt`: validate → control (not approved) →
   state-only forge → real runtime reports Approved by a forged approver → downstream
   action proceeds.

Not a gated crypto-only claim (it needs a running Dolibarr+PostgreSQL). It is the
native-tier upgrade of the Dolibarr Layer-2 row.
