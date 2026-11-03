/**
 * Approval workflow on n8n's execution engine.
 *
 * A Gate node's output records the approval decision; an Execute node downstream runs
 * the transfer only if the Gate output says approved. n8n persists each node's output
 * in the execution record (execution_entity.data.resultData.runData) and, on resume,
 * feeds a node's persisted output to its children. This module drives the real engine
 * path (WorkflowExecute.runPartialWorkflow2) that consumes that persisted runData.
 */
const { Workflow, NodeConnectionTypes } = require('n8n-workflow');
const { WorkflowExecute } = require('n8n-core');

const START_AMOUNT = 100000;
const GATE = 'Gate';
const EXECUTE = 'Execute';
const SIGNATURE_FIELD = 'approval_signature';

const gateNode = {
  description: {
    displayName: 'Gate', name: 'gate', group: ['transform'], version: 1,
    description: 'approval gate', defaults: { name: GATE },
    inputs: [NodeConnectionTypes.Main], outputs: [NodeConnectionTypes.Main], properties: [],
  },
  async execute() { return [[{ json: { approved: false, approver: '' } }]]; },
};

const executeNode = {
  description: {
    displayName: 'Execute', name: 'execute', group: ['transform'], version: 1,
    description: 'execute transfer', defaults: { name: EXECUTE },
    inputs: [NodeConnectionTypes.Main], outputs: [NodeConnectionTypes.Main], properties: [],
  },
  async execute() {
    const json = this.getInputData()[0].json;
    const message = json.approved
      ? `[EXECUTED] Wire transfer of $${START_AMOUNT.toLocaleString()}.00 to ACME-CORP; approved by ${json.approver || 'unnamed'}.`
      : '[BLOCKED] Transfer rejected; gate output approved=false.';
    return [[{ json: { result: message, executed: !!json.approved, approver: json.approver || '' } }]];
  },
};

const nodeTypes = {
  getByName(t) { return this.getByNameAndVersion(t); },
  getByNameAndVersion(t) { return t === 'gate' ? gateNode : t === 'execute' ? executeNode : undefined; },
};

function buildWorkflow() {
  const nodes = [
    { id: 'g', name: GATE, type: 'gate', typeVersion: 1, position: [0, 0], parameters: {} },
    { id: 'e', name: EXECUTE, type: 'execute', typeVersion: 1, position: [1, 0], parameters: {} },
  ];
  const connections = { [GATE]: { main: [[{ node: EXECUTE, type: 'main', index: 0 }]] } };
  return new Workflow({ id: 'wire-transfer', name: 'wire-transfer', nodes, connections, active: false, nodeTypes });
}

const additionalData = {
  credentialsHelper: { getDecrypted: async () => ({}), getCredentials: async () => ({}), authenticate: async (_c, r) => r },
  hooks: { runHook: async () => {}, executeHookFunctions: async () => {} },
  executeWorkflow: async () => ({}),
  restApiUrl: '', instanceBaseUrl: '', formWaitingBaseUrl: '', webhookBaseUrl: '',
  webhookWaitingBaseUrl: '', webhookTestBaseUrl: '', currentNodeParameters: undefined,
  executionId: 'execution-1', userId: 'operator', variables: {},
  setExecutionStatus() {}, sendDataToUI() {},
};

/** The persisted execution data for a transfer whose gate output is unapproved. */
function initialRunData(amount = START_AMOUNT, recipient = 'ACME-CORP') {
  return {
    [GATE]: [{ startTime: 0, executionTime: 0, source: [],
      data: { main: [[{ json: { approved: false, approver: '', amount, recipient } }]] } }],
  };
}

function gateJson(runData) {
  return runData[GATE][0].data.main[0][0].json;
}

async function settle(runData) {
  const gate = gateJson(runData);
  const approver = gate.approver || '';


  const we = new WorkflowExecute(additionalData, 'manual');
  const data = await we.runPartialWorkflow2(buildWorkflow(), runData, {}, [], { nodeName: EXECUTE, mode: 'inclusive' });
  const out = data.data.resultData.runData[EXECUTE][0].data.main[0][0].json;
  return {
    status: out.executed ? 'EXECUTED' : 'REJECTED',
    executed: !!out.executed,
    approved: !!gate.approved,
    approver: out.approver || approver,
    message: out.result,
  };
}

module.exports = {
  START_AMOUNT, GATE, EXECUTE, SIGNATURE_FIELD,
  buildWorkflow, additionalData, initialRunData, gateJson, settle,
};
