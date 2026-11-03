/**
 * A JSON-file store for persisted n8n execution data (resultData.runData).
 *
 * This stands in for the `data` column of n8n's execution_entity row, which holds the
 * serialized run state that the engine restores on resume.
 */
const fs = require('fs');

class RunDataStore {
  constructor(path) { this.path = path; }
  save(runData) { fs.writeFileSync(this.path, JSON.stringify(runData)); }
  load() { return JSON.parse(fs.readFileSync(this.path, 'utf8')); }
  exists() { return fs.existsSync(this.path); }
}

module.exports = { RunDataStore, openStore: (p) => new RunDataStore(p) };
