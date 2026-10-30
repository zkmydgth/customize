// 批量求值：node test_runner.js cases.json  ->  [{id, runs:[{ok, vals|err}]}]
const fs = require('fs');
const JQRT = require('./jq_runtime.js');

const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = [];
for (const c of cases) {
  const run = JQRT.make(c.ast);
  const runs = [];
  for (const inp of c.inputs) {
    try {
      const vals = run(inp).map(x => JSON.stringify(x));
      runs.push({ ok: true, vals });
    } catch (e) {
      runs.push({ ok: false, err: String((e && e.message) || e) });
    }
  }
  out.push({ id: String(c.id), runs });
}
process.stdout.write(JSON.stringify(out));
