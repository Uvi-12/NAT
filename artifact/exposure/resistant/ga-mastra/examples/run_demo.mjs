/**
 * Resistance demonstration: the snapshot forge that succeeds against checkpoint-trusting
 * frameworks is ineffective against Mastra, because resume re-derives the decision from
 * validated live input.
 */
import { tmpdir } from 'os';
import { join } from 'path';
import { existsSync, rmSync } from 'fs';
import { startTransfer } from '../src/workflow.mjs';
import { forgePersistedApproval } from '../src/forge.mjs';
import { resumeWithoutDecision, resumeWithDecision } from '../src/resume.mjs';

const DB = join(tmpdir(), 'ga_mastra_demo.db');
if (existsSync(DB)) rmSync(DB);

const APPROVER = 'Rahul S. (Senior Compliance Officer) [14:32:01]';

console.log('== start ==');
const { runId, status } = await startTransfer(DB);
console.log(`started run=${runId.slice(0, 8)} status=${status}`);

console.log('== forge snapshot (set persisted output approved=true) ==');
const forged = await forgePersistedApproval(DB, runId, APPROVER);
console.log(`persisted output now: approved=${forged.suspendOutput.approved} approver=${JSON.stringify(forged.suspendOutput.approver)}`);

console.log('== resume relying on the forged snapshot (no live decision) ==');
const r1 = await resumeWithoutDecision(DB, runId);
console.log(`  status=${r1.status} executed=${r1.executed}`);
console.log(`  ${r1.message}`);

console.log('== resume with a live decision = REJECT (forged output present) ==');
const r2 = await resumeWithDecision(DB, runId, { approved: false, approver: 'human-REJECT' });
console.log(`  status=${r2.status} executed=${r2.executed}`);
console.log(`  ${r2.message}`);

console.log('\nResult: the forged persisted approval is never honoured; the decision');
console.log('is taken from the live, schema-validated resumeData. Mastra resists the forge.');
