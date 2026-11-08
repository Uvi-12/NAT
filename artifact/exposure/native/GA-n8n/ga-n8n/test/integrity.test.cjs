/**
 * Integrity tests for the n8n execution-data approval surface.
 *
 * Binary property: an unapproved persisted gate output keeps the transfer blocked;
 * forging the persisted gate output to approved=true causes execution on resume. The resume path
 * is the real WorkflowExecute.runPartialWorkflow2 engine call.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const os = require('os');
const path = require('path');
const fs = require('fs');
const { randomUUID } = require('crypto');
const { initialRunData, settle } = require('../src/workflow.cjs');
const { openStore } = require('../src/store.cjs');
const { injectApproval } = require('../src/forge.cjs');


function store() {
  const p = path.join(os.tmpdir(), `ga_n8n_test_${randomUUID()}.json`);
  return { s: openStore(p), p };
}
function cleanup(p) { if (fs.existsSync(p)) fs.rmSync(p); }

test('control: unapproved gate output stays blocked', async () => {
  const { s, p } = store();
  try {
    s.save(initialRunData());
    const r = await settle(s.load());
    assert.equal(r.executed, false);
    assert.equal(r.status, 'REJECTED');
  } finally { cleanup(p); }
});

test('forged gate output executes on resume', async () => {
  const { s, p } = store();
  try {
    s.save(initialRunData());
    injectApproval(s, 'Amit K.');
    const r = await settle(s.load());
    assert.equal(r.approved, true);
    assert.equal(r.executed, true);
  } finally { cleanup(p); }
});

test('forged approver is recorded in the executed result', async () => {
  const { s, p } = store();
  try {
    s.save(initialRunData());
    const name = 'Vikram P. (Senior Compliance Officer) [14:32:01]';
    injectApproval(s, name);
    const r = await settle(s.load());
    assert.equal(r.approver, name);
    assert.ok(r.message.includes(name));
  } finally { cleanup(p); }
});

for (let i = 0; i < 5; i++) {
  test(`forge is deterministic (run ${i})`, async () => {
    const { s, p } = store();
    try {
      s.save(initialRunData());
      injectApproval(s, 'Raj M.');
      const r = await settle(s.load());
      assert.equal(r.executed, true);
    } finally { cleanup(p); }
  });
}

