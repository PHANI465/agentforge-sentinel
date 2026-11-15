// Usage: node public_site/tests/document-evidence.browser.mjs <web/node_modules>
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {resolve, join} from 'node:path';

if (!process.argv[2]) throw new Error('Pass the installed web/node_modules directory.');
const {chromium} = createRequire(join(resolve(process.argv[2]), 'package.json'))('playwright');
const source = await readFile(new URL('../static/document-evidence.mjs', import.meta.url));
const server = createServer((request, response) => {
  if (request.url === '/document-evidence.mjs') {
    response.writeHead(200, {'Content-Type': 'text/javascript'}).end(source);
  } else if (request.url === '/') {
    response.writeHead(200, {'Content-Type': 'text/html'}).end('<!doctype html><title>Evidence runtime check</title>');
  } else response.writeHead(404).end();
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
  browser = await chromium.launch();
  const page = await browser.newPage();
  const requests = [];
  page.on('request', request => requests.push(request.url()));
  const origin = 'http://127.0.0.1:' + server.address().port;
  await page.goto(origin);
  const output = await page.evaluate(async () => {
    const api = await import('/document-evidence.mjs');
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',
      new TextEncoder().encode('synthetic'))), byte => byte.toString(16).padStart(2, '0')).join('');
    const review = api.createEvidenceReview({reviewId: 'browser_review',
      documents: [{id: 'doc', sha256: digest, format: 'pdf', bytes: 9}],
      facts: ['opening_balance', 'total_credits', 'total_debits', 'closing_balance'].map((field, index) => ({
        id: 'f' + index, documentId: 'doc', statementId: 's', field, currency: 'USD',
        amount: ['1000', '500', '200', '900'][index], certainty: 'extracted',
        location: {page: 1, line: index + 1}, excerpt: field,
      }))});
    const result = api.reconcileStatement(review, {documentId: 'doc', statementId: 's', currency: 'USD'});
    return {result, frozen: Object.isFrozen(review.facts[0]), storage: localStorage.length + sessionStorage.length};
  });
  assert.equal(output.result.calculation.signedDifference, '-400.00');
  assert.equal(output.result.status, 'flagged');
  assert.equal(output.frozen, true);
  assert.equal(output.storage, 0);
  assert.ok(requests.every(url => url === origin + '/' || url === origin + '/document-evidence.mjs'));
  console.log('PASS: Chromium module, Web Crypto, exact reconciliation, frozen evidence, no storage/outbound requests');
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
}
