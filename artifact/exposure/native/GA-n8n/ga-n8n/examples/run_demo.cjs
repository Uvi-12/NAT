/** Run the end-to-end demonstration against a temporary execution-data file. */
process.argv = [process.argv[0], process.argv[1], 'demo'];
require('../src/cli.cjs');
