/**
 * Command-line interface for the n8n execution-data integrity demonstration.
 *
 * Commands: demo | start | status | forge | resume
 */
const os = require('os');
const path = require('path');
const fs = require('fs');
const { START_AMOUNT, initialRunData, gateJson, settle } = require('./workflow.cjs');
const { openStore } = require('./store.cjs');
const { injectApproval } = require('./forge.cjs');

const DEFAULT_DB = path.join(os.tmpdir(), 'ga_n8n_rundata.json');
const DEFAULT_APPROVER = 'Rahul S. (Senior Compliance Officer) [14:32:01]';

function arg(name, fallback) {
  const i = process.argv.indexOf(name);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

const DB = arg('--db', DEFAULT_DB);
const APPROVER = arg('--approver', DEFAULT_APPROVER);

async function cmdStart() {
  openStore(DB).save(initialRunData(START_AMOUNT, arg('--recipient', 'ACME-CORP')));
  console.log(`started transfer amount=$${START_AMOUNT.toLocaleString()}.00 status=unapproved (awaiting approval)`);
}

function cmdStatus() {
  const store = openStore(DB);
  if (!store.exists()) return console.log('no execution data found');
  const gate = gateJson(store.load());
  console.log(`approved=${gate.approved} approver=${JSON.stringify(gate.approver || '')}`);
}

function cmdForge() {
  const store = openStore(DB);
  if (!store.exists()) return console.log('no execution data found');
  injectApproval(store, APPROVER);
  console.log(`forged persisted gate output approved=true approver=${JSON.stringify(APPROVER)}`);
}

async function cmdResume() {
  const store = openStore(DB);
  if (!store.exists()) return console.log('no execution data found');
  const result = await settle(store.load());
  console.log(`resumed status=${result.status} approved=${result.approved} executed=${result.executed} approver=${JSON.stringify(result.approver)}`);
  console.log(`  ${result.message}`);
}

async function cmdDemo() {
  if (fs.existsSync(DB)) fs.rmSync(DB);
  console.log('== start ==');            await cmdStart();
  console.log('== resume (control) =='); await cmdResume();
  console.log('== forge ==');            cmdForge();
  console.log('== resume ==');           await cmdResume();
}

const command = process.argv[2];
const table = { start: cmdStart, status: cmdStatus, forge: cmdForge, resume: cmdResume, demo: cmdDemo };
(async () => {
  const fn = table[command];
  if (!fn) { console.error(`usage: node src/cli.cjs <${Object.keys(table).join('|')}> [--db PATH] [--approver NAME]`); process.exit(2); }
  await fn();
  process.exit(0);
})().catch((e) => { console.error(e.message); process.exit(1); });
