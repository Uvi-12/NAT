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
  const full = { ...record, system, shape: record.shape || "REBIND", approver: APPROVER, a_args: A_ARGS, b_args: B_ARGS };
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
export const verdictRebind = (rebindFired)=>verdictFromState(rebindFired);
export function verdictFromState(replayFired, hardenedBlocked) {
  return replayFired ? "EXPOSED" : "RESISTANT";
}
