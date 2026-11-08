// APF / APF - LAUNDER live harness: Inngest (#29).
// The payment gate is step.waitForEvent correlated by data.runId in engine-owned step state. A
// foreign Blackwell run CANNOT re-parent onto another run's genuine approval: presenting the
// Meridian approval (runId=A) to the Blackwell run (runId=L) fails the match, so the Blackwell run
// stays suspended and never pays. An approval is bound to the run it was issued for; no foreign
// execution can inherit it. EXPECTED: RESISTANT (launder_fired=False). Consistent with Inngest
// REBIND=RESISTANT and SUPPRESS=RESISTANT.
import { Inngest } from "inngest";
import * as C from "./apf_common.mjs";
import path from "node:path";
import { fileURLToPath } from "node:url";
const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(process.env.APF_EVIDENCE_BASE || path.join(HERE, "..", "evidence"), "29_inngest");
const inngest = new Inngest({ id: "apf-harness", isDev: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function result(runId) { try { const r = await fetch(`http://localhost:3000/result/${runId}`); return await r.json(); } catch { return null; } }
async function waitResult(runId, tries = 20) { for (let i = 0; i < tries; i++) { const r = await result(runId); if (r) return r; await sleep(1000); } return null; }

async function main() {
  const audit = [];
  // control: genuine approval for run A (Meridian) -> pays
  await inngest.send({ name: "apf/payment.requested", data: { runId: "A", ...C.A_ARGS } });
  await sleep(1500);
  await inngest.send({ name: "apf/approval", data: { runId: "A", approved: true, approver: C.APPROVER } });
  const resA = await waitResult("A");
  if (resA && resA.paid) audit.push({ action: "execute_payment", amount: resA.amount, beneficiary: resA.beneficiary, approved_by_in_audit: resA.approver });
  C.line("control", `genuine approval for run A -> ${JSON.stringify(resA)}`);
  C.line("audit", "the gate is step.waitForEvent correlated by data.runId; an approval is bound to the run it names, in engine-owned step state");

  // launder: a foreign Blackwell run (runId=L) tries to re-parent onto run A's genuine Meridian
  // approval by re-presenting it. The gate matches on data.runId and the approval carries runId=A,
  // so it does NOT resume run L. A foreign run cannot inherit another run's engine-owned approval.
  await inngest.send({ name: "apf/payment.requested", data: { runId: "L", ...C.B_ARGS } });
  await sleep(1500);
  await inngest.send({ name: "apf/approval", data: { runId: "A", approved: true, approver: C.APPROVER } });  // the Meridian approval, re-presented
  const resL = await waitResult("L", 8);
  const launderFired = !!(resL && resL.paid && resL.beneficiary === C.B_ARGS.beneficiary);
  C.line("launder", `Meridian approval (runId=A) presented to foreign run L -> ${JSON.stringify(resL)} (null/paid:false = resisted)`);

  const nonce = "n-launder-0029";
  const verdict = C.verdictLaunder(launderFired);
  C.line("verdict", verdict);
  const h = C.emitEvidence("Inngest", OUT, {
    shape: "LAUNDER",
    restore_path: "the approval gate is an engine-enforced step.waitForEvent correlated by data.runId; an approval is bound to the run it names, and a foreign run cannot inherit it (the match fails)",
    execution_tier: "live (real Inngest dev server; served function)",
    why_resistant: "the approval carries the run id it was issued for; presenting it to a foreign run fails the engine-owned match, so the foreign run never pays; the only approval that resumes a run is one issued for that run",
    approval_issued_for: C.A_ARGS, foreign_action: C.B_ARGS,
    launder_fired: launderFired, laundered_payment: null,
    audit_ledger: audit, verdict,
  });
  console.log("EVIDENCE_HASH16", h);
}
main().catch((e) => { console.error(e); process.exit(0); });
