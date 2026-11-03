// APF / APF - REPLAY live harness: Inngest (#29)
// Drives the REAL Inngest dev server. Approval = an apf/approval event; the function's
// waitForEvent matches on data.runId, so only an approval carrying a run's own id resumes
// it. Confirms live that reusing run A's approval (runId "A") does not resume run B
// (runId "B"). EXPECTED: RESISTANT (replay_fired = false).
import { Inngest } from "inngest";
import * as C from "./apf_common.mjs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.join(process.env.APF_EVIDENCE_BASE || path.join(HERE, "..", "evidence"), "29_inngest");
const inngest = new Inngest({ id: "apf-harness", isDev: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function result(runId) {
  try {
    const r = await fetch(`http://localhost:3000/result/${runId}`);
    return await r.json();
  } catch { return null; }
}
async function waitResult(runId, tries = 20) {
  for (let i = 0; i < tries; i++) { const r = await result(runId); if (r) return r; await sleep(1000); }
  return null;
}

async function main() {
  const audit = [];

  // ---- control: genuine approval for run A ----
  await inngest.send({ name: "apf/payment.requested", data: { runId: "A", ...C.A_ARGS } });
  await sleep(1500);
  await inngest.send({ name: "apf/approval", data: { runId: "A", approved: true, approver: C.APPROVER } });
  const resA = await waitResult("A");
  if (resA && resA.paid) audit.push({ action: "execute_payment", amount: resA.amount, beneficiary: resA.beneficiary, approved_by_in_audit: resA.approver });
  C.line("control", `genuine approval for run A -> ${JSON.stringify(resA)}`);

  // ---- replay: run B; reuse run A's approval (runId "A") ----
  await inngest.send({ name: "apf/payment.requested", data: { runId: "B", ...C.B_ARGS } });
  await sleep(1500);
  await inngest.send({ name: "apf/approval", data: { runId: "A", approved: true, approver: C.APPROVER } }); // matches A, not B
  const resB = await waitResult("B", 8);
  const replayFired = !!(resB && resB.paid && resB.beneficiary === C.B_ARGS.beneficiary);
  const bRow = replayFired ? { action: "execute_payment", amount: resB.amount, beneficiary: resB.beneficiary, approved_by_in_audit: resB.approver } : null;
  C.line("audit", "waitForEvent matches on data.runId; run B awaits an approval with runId 'B'");
  C.line("replay", `reused run A approval (runId A) onto run B -> ${JSON.stringify(resB) || "still awaiting (not paid)"}`);

  const seen = new Set(); const nonce = "n-runA-0029";

  const verdict = C.verdictFromState(replayFired);
  C.line("verdict", verdict);
  const h = C.emitEvidence("Inngest", OUT, {
    restore_path: "approval = event resumed via waitForEvent with run-scoped match (data.runId)",
    execution_tier: "live (real Inngest dev server; served function)",
    why_resistant: "run B awaits an approval carrying its own runId; run A's approval (runId A) does not match run B",
    genuine_run: "A", replay_run: "B",
    replay_fired: replayFired, replayed_payment: bRow,
    audit_ledger: audit, verdict,
  });
  console.log("EVIDENCE_HASH16", h);
}
C.guardedMain("Inngest", OUT, main);
