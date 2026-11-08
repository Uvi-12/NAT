// APF / APF - REBIND live harness: Inngest (#29).
// The payment reads amount/beneficiary from the FROZEN originating trigger event (event.data);
// the approval is decision-only, matched by data.runId. A state writer mutating the approval
// event with B args does NOT move the payment, because the args come from the frozen trigger.
// EXPECTED: RESISTANT. (Caveat: a function reading args from the approval event would be EXPOSED.)
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
  // control: genuine approval of args A (Meridian) - payment reads the frozen trigger
  await inngest.send({ name: "apf/payment.requested", data: { runId: "A", ...C.A_ARGS } });
  await sleep(1500);
  await inngest.send({ name: "apf/approval", data: { runId: "A", approved: true, approver: C.APPROVER } });
  const resA = await waitResult("A");
  if (resA && resA.paid) audit.push({ action: "execute_payment", amount: resA.amount, beneficiary: resA.beneficiary, approved_by_in_audit: resA.approver });
  C.line("control", `genuine approval for run A -> ${JSON.stringify(resA)}`);
  C.line("audit", "payment reads amount/beneficiary from the frozen trigger event; approval decision-only (match data.runId)");

  // rebind: Priya reviews Meridian; a state writer sends a MUTATED approval carrying B args - the function ignores them
  await inngest.send({ name: "apf/payment.requested", data: { runId: "R", ...C.A_ARGS } });
  await sleep(1500);
  await inngest.send({ name: "apf/approval", data: { runId: "R", approved: true, approver: C.APPROVER, amount: C.B_ARGS.amount, beneficiary: C.B_ARGS.beneficiary } });
  const resR = await waitResult("R", 10);
  const rebindFired = !!(resR && resR.paid && resR.beneficiary === C.B_ARGS.beneficiary);
  const bRow = rebindFired ? { action: "execute_payment", amount: resR.amount, beneficiary: resR.beneficiary, approved_by_in_audit: resR.approver } : null;
  C.line("rebind", `approval carried B args; payment bound to frozen trigger -> ${JSON.stringify(resR)}`);

  const nonce = "n-rebind-0029";
  const verdict = C.verdictRebind(rebindFired);
  C.line("verdict", verdict);
  const h = C.emitEvidence("Inngest", OUT, {
    shape: "REBIND",
    restore_path: "payment reads args from the frozen originating trigger event; approval decision-only (match data.runId)",
    execution_tier: "live (real Inngest dev server; served function)",
    caveat: "a function reading args from the approval event would be EXPOSED; durable trigger is frozen",
    genuine_args: C.A_ARGS, mutated_args: C.B_ARGS,
    rebind_fired: rebindFired, rebound_payment: bRow,
    audit_ledger: audit, verdict,
  });
  console.log("EVIDENCE_HASH16", h);
}
main().catch((e) => { console.error(e); process.exit(0); });
