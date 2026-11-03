# Coverage, Layer-2 native-promotion kit

29 apps. Expected verdicts: {'EXPOSED': 26, 'RESISTANT': 3}. Confidence: {'high': 1, 'medium': 14, 'low': 14}.

Confidence = how direct the forge is on a typical Docker host: **high** = official image + known approval column + direct write, **medium** = official image, schema/seed is version-dependent, **low** = heavy stack (k8s / multi-service / CA bootstrap) that may record INCONCLUSIVE if it can't come up. Every harness records a real verdict or INCONCLUSIVE+reason, never a forced pass.

| id | system | expected | confidence | forge target |
| --- | --- | --- | --- | --- |
| L2-15 | Odoo Community | EXPOSED | high | purchase.order.state == 'purchase' |
| L2-03 | Consul Democracy | EXPOSED | medium | budget_investments.selected == true |
| L2-04 | Decidim | EXPOSED | medium | decidim_authorizations.granted_at IS NOT NULL |
| L2-05 | Your Priorities | EXPOSED | medium | posts.official_status == 2 (successful) |
| L2-06 | Documenso | EXPOSED | medium | Document/Envelope.status == 'COMPLETED' |
| L2-07 | DocuSeal | EXPOSED | medium | submitters.completed_at IS NOT NULL |
| L2-09 | Mayan EDMS | EXPOSED | medium | workflow instance current state (last transition destination |
| L2-10 | OpenSign | EXPOSED | medium | contracts_Document.IsCompleted == true |
| L2-11 | Apache OFBiz | EXPOSED | medium | OrderHeader.statusId == 'ORDER_APPROVED' |
| L2-13 | ERPNext | EXPOSED | medium | tabPurchase Order.docstatus == 1 (Submitted) |
| L2-17 | Apache Fineract | EXPOSED | medium | m_loan.loan_status_id == 200 (APPROVED) |
| L2-21 | OpenHIM | EXPOSED | medium | transactions.status == 'Successful' trusted by routing |
| L2-22 | OpenEMR | EXPOSED | medium | billing.authorized == 1 releases the claim/billing path |
| L2-30 | Galaxy | EXPOSED | medium | history.published / importable boolean -> world-importable |
| L2-33 | Grafeas | EXPOSED | medium | ATTESTATION occurrence trusted as a plain row, embedded sign |
| L2-01 | Argo Workflows | EXPOSED | low | suspend node status -> Succeeded (state-only, no argo resume |
| L2-02 | Spinnaker | EXPOSED | low | Orca stage context judgmentStatus = Continue (state-only) |
| L2-08 | LibreSign | RESISTANT | low | PAdES signature re-parsed from the PDF and verified against  |
| L2-14 | LedgerSMB | EXPOSED | low | transactions.approved == true |
| L2-18 | care (OHC Network) | EXPOSED | low | facility_shiftingrequest.status == approved releases transfe |
| L2-19 | DHIS2 | EXPOSED | low | a dataapproval row marks data approved (locked/released) |
| L2-20 | OpenELIS Global | EXPOSED | low | analysis.status_id == finalized releases the result |
| L2-23 | Dogtag PKI | RESISTANT | low | agent approval re-derived at issuance, persisted request sta |
| L2-24 | EJBCA (approval gate) | EXPOSED | low | ApprovalData.status == STATUS_APPROVED (0) |
| L2-25 | OpenBao (control-group) | EXPOSED | low | control-group Authorizations present |
| L2-28 | Dataverse | EXPOSED | low | datasetversion.versionstate == 'RELEASED' |
| L2-29 | eLabFTW | RESISTANT | low | RFC-3161 trusted-timestamp token / libsodium signature re-ve |
| L2-31 | InvenioRDM | EXPOSED | low | access.protection.record == 'public' |
| L2-32 | OSF | EXPOSED | low | is_public / sanction.state == 'APPROVED' |
