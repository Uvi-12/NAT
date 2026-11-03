// Shared APF replay-harness helpers (Batch 2, Node agentic). Mirrors apf_common.py.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

export const APPROVER = "Priya";
export const A_ARGS = { amount: 50000, beneficiary: "Meridian Supplies Ltd" };
export const B_ARGS = { amount: 250000, beneficiary: "Blackwell Trading LLC" };

// canonical JSON: sorted keys, compact
export function canon(obj) {
  if (obj === null || typeof obj !== "object") return JSON.stringify(obj);
  if (Array.isArray(obj)) return "[" + obj.map(canon).join(",") + "]";
  const keys = Object.keys(obj).sort();
  return "{" + keys.map(k => JSON.stringify(k) + ":" + canon(obj[k])).join(",") + "}";
}
export function argsHash(args) {
  return crypto.createHash("sha256").update(canon(args)).digest("hex");
}
export function line(label, value) {
  console.log(label.padStart(10) + " | " + (typeof value === "string" ? value : JSON.stringify(value)));
}
export function emitEvidence(system, outdir, record) {
  fs.mkdirSync(outdir, { recursive: true });
  const full = { ...record, system, shape: "replay", approver: APPROVER, a_args: A_ARGS, b_args: B_ARGS };
  // stable stringify (sorted keys) to match python json.dumps(sort_keys, indent2) style digest scheme:
  const blob = JSON.stringify(sortDeep(full), null, 2);
  fs.writeFileSync(path.join(outdir, "evidence.json"), blob);
  const digest = crypto.createHash("sha256").update(blob).digest("hex");
  fs.writeFileSync(path.join(outdir, "evidence.sha256"), digest + "\n");
  return digest.slice(0, 16);
}
function sortDeep(o) {
  if (Array.isArray(o)) return o.map(sortDeep);
  if (o && typeof o === "object") {
    const out = {};
    for (const k of Object.keys(o).sort()) out[k] = sortDeep(o[k]);
    return out;
  }
  return o;
}
export function verdictFromState(replayFired, hardenedBlocked) {
  return replayFired ? "EXPOSED" : "RESISTANT";
}

export function guardedMain(system, outdir, mainFn, diagGetter) {
  // Always writes an evidence file; on any error emits INCONCLUSIVE with the reason.
  Promise.resolve().then(mainFn).catch((e) => {
    const rec = {
      execution_tier: "live (failed before verdict)",
      verdict: "INCONCLUSIVE",
      error: `${e && e.name ? e.name : "Error"}: ${e && e.message ? e.message : e}`,
      stack_tail: e && e.stack ? String(e.stack).split("\n").slice(0, 8) : [],
      replay_fired: false, hardened_blocked: null, audit_ledger: [],
    };
    if (diagGetter) { try { rec.diagnostics = diagGetter(); } catch (_) {} }
    try {
      const h = emitEvidence(system, outdir, rec);
      console.log("EVIDENCE_HASH16", h);
      console.log("GUARD wrote INCONCLUSIVE evidence after error:", rec.error);
    } catch (e2) { console.log("GUARD failed to write evidence:", e2); }
  });
}
