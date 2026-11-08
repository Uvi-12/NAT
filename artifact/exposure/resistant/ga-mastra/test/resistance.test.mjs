/**
 * Resistance tests: forging the persisted snapshot output does NOT cause execution,
 * and a live decision overrides any forged persisted output. These encode the
 * experiments that classify Mastra as resistant under the Decision-Provenance
 * Integrity predicate (decision re-derived from validated live input on resume).
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { tmpdir } from 'os';
import { join } from 'path';
import { existsSync, rmSync } from 'fs';
import { randomUUID } from 'crypto';
import { startTransfer } from '../src/workflow.mjs';
import { forgePersistedApproval } from '../src/forge.mjs';
import { resumeWithoutDecision, resumeWithDecision } from '../src/resume.mjs';

function freshDb() {
  const db = join(tmpdir(), `ga_mastra_test_${randomUUID()}.db`);
  if (existsSync(db)) rmSync(db);
  return db;
}

test('forged persisted output without a live decision does not execute', async () => {
  const db = freshDb();
  const { runId } = await startTransfer(db);
  await forgePersistedApproval(db, runId, 'Amit K.');
  const r = await resumeWithoutDecision(db, runId);
  assert.equal(r.executed, false);
  assert.equal(r.status, 'REJECTED');
});

test('live decision overrides a forged persisted approval', async () => {
  const db = freshDb();
  const { runId } = await startTransfer(db);
  await forgePersistedApproval(db, runId, 'Vikram P.');
  const r = await resumeWithDecision(db, runId, { approved: false, approver: 'human-REJECT' });
  assert.equal(r.executed, false);
});

test('a legitimate live approval executes (sanity: the workflow is functional)', async () => {
  const db = freshDb();
  const { runId } = await startTransfer(db);
  const r = await resumeWithDecision(db, runId, { approved: true, approver: 'Suresh R.' });
  assert.equal(r.executed, true);
});
