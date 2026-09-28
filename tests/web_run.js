// Helper for tests/test_web.py: run the browser sorter core under Node.
// usage: node web_run.js rules.json emailfile  -> prints JSON results
const fs = require('fs');
const path = require('path');
const core = require(path.join(__dirname, '..', 'web', 'sorter_core.js'));

(async () => {
  const [rulesPath, emailPath] = process.argv.slice(2);
  const rules = JSON.parse(fs.readFileSync(rulesPath, 'utf8'));
  const sorter = core.createSorter(rules);
  const file = await fs.openAsBlob(emailPath);
  const result = await sorter.run(file);
  const rows = result.allCsv.join('');
  process.stdout.write(JSON.stringify({
    total: result.total,
    counts: Object.fromEntries(result.counts),
    csv: rows,
    replies: sorter.replyPageData(result.replyItems, rules.signature),
  }));
})().catch((err) => { console.error(err); process.exit(1); });
