import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {createServer} from 'node:http';
import {mkdir, readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {extname, join, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {expected} from './insights-expected.mjs';
import {samples} from '../static/insight-samples.mjs';
import {strToU8, zipSync} from '../static/vendor/fflate.mjs';

const [modules, output] = process.argv.slice(2);
if (!modules || !output) throw new Error('Pass installed web/node_modules and a QA output directory.');
await mkdir(output, {recursive: true});
const {chromium} = createRequire(join(resolve(modules), 'package.json'))('playwright');
const root = fileURLToPath(new URL('../static/', import.meta.url));
const assets = {'/': '/index.html'};
const mime = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.mjs': 'text/javascript',
  '.svg': 'image/svg+xml', '.pdf': 'application/pdf', '.woff2': 'font/woff2'};
const server = createServer(async (request, reply) => {
  const key = new URL(request.url, 'http://localhost').pathname;
  const file = resolve(root, '.' + (assets[key] ?? key));
  if (!file.startsWith(resolve(root) + sep)) return reply.writeHead(404).end();
  try {
    const data = await readFile(file);
    reply.writeHead(200, {'Content-Type': mime[extname(file)] ?? 'application/octet-stream'}).end(data);
  } catch { reply.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = 'http://127.0.0.1:' + server.address().port;
const manifest = JSON.parse(await readFile(join(root, 'samples/insights/manifest.json'), 'utf8'));
for (const [name, record] of Object.entries(manifest.files)) {
  const file = await readFile(join(root, 'samples/insights', name));
  assert.equal(file.length, record.bytes);
  assert.equal(createHash('sha256').update(file).digest('hex'), record.sha256);
}
const browser = await chromium.launch();
try {
  const context = await browser.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
  const book = [];
  const errors = [];
  // Context events include worker requests that are outside the page's request stream.
  context.on('request', request => book.push([request.method(), request.url(), request.postData()]));
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(String(error)));
  await page.goto(origin);
  const review = page.getByRole('button', {name: 'Try the sample'});
  const picker = page.locator('#pdf-file');
  const chosen = page.getByLabel('Sample document');
  const results = page.locator('#results');
  async function choose(key) {
    await chosen.selectOption(key);
    await review.click();
    await page.getByText('Synthetic sample reviewed.', {exact: true}).waitFor();
  }
  let resultChecks = 0;
  for (const [key, cases] of expected) {
    await choose(key);
    for (const [id, state, text] of cases) {
      const result = results.locator('[data-detector=' + id + '][data-outcome=' + state + ']').filter({hasText: text});
      assert.equal(await result.count(), 1, key + ' ' + id + ': ' + await results.innerText());
      resultChecks++;
    }
    if (key.endsWith('control')) assert.equal(await results.locator('[data-outcome=flagged]').count(), 0, key);
  }
  for (const [key, codes, difference] of [['invoice', ['line-math','total-math'], '10.00'],
    ['invoicecontrol', [], '']]) {
    await choose(key);
    assert.deepEqual(await results.locator('[data-check]').evaluateAll(nodes => nodes.map(node => node.dataset.check)), codes);
    if (difference) assert.ok((await results.innerText()).includes(difference));
  }
  const upload = page.getByRole('button', {name: /^(Review this file|Compare these files)$/});
  const ready = page.getByText('Document reviewed in this browser.', {exact: true});
  const purchase = samples.purchase.files.map(file => join(root, file));
  const beforeUpload = book.length;
  await picker.setInputFiles(purchase);
  await upload.click();
  await ready.waitFor();
  assert.equal(await results.locator('[data-detector=D09][data-outcome=not-run]').count(), 1);
  await page.getByText('Comparison settings', {exact:true}).click();
  await page.getByLabel('Trusted vendor baseline').selectOption('doc_4');
  assert.equal(await results.innerText(), '');
  await upload.click();
  await ready.waitFor();
  assert.equal(await results.locator('[data-detector=D09][data-outcome=flagged]').count(), 1);
  assert.ok(book.slice(beforeUpload).every(([, url]) => !url.includes('/samples/')));
  const priceCheck = results.locator('[data-detector=D06]').first();
  const source = priceCheck.getByRole('button', {name: /Document 2.*Record, row 5, column 2/});
  await source.focus();
  await page.keyboard.press('Enter');
  assert.equal(await results.locator('.source-excerpt').first().evaluate(node => document.activeElement === node), true);
  assert.match(await results.locator('.source-excerpt').first().innerText(), /VALVE-KIT.*200 ea 100.00/);
  await page.keyboard.press('Tab');
  await page.keyboard.press('Enter');
  assert.equal(await source.evaluate(node => document.activeElement === node), true);
  await page.screenshot({path: join(output, 'comparison-1440.png'), fullPage: true});
  await picker.setInputFiles(samples.policy.files.map(file => join(root, file)));
  await page.getByLabel('Approval threshold (optional)').fill('5000.00');
  await upload.click();
  await ready.waitFor();
  assert.equal(await results.locator('[data-detector=D10][data-outcome=flagged]').count(), 1);
  await picker.setInputFiles(Array.from({length: 3}, (_, index) => ({
    name: 'aggregate-' + index + '.pdf', mimeType: 'application/pdf', buffer: Buffer.alloc(7_000_000),
  })));
  await upload.click();
  await page.getByRole('alert').getByText(/20 MB together/).waitFor();

  let observed;
  const started = new Promise(resolve => { observed = resolve; });
  const held = [];
  await page.route('**/samples/insights/statement-review.pdf', route => {
    held.push(route);
    observed();
  });
  await chosen.selectOption('statementgap');
  await review.click();
  await started;
  await page.getByRole('button', {name: 'Cancel', exact: true}).click();
  await page.unroute('**/samples/insights/statement-review.pdf');
  await Promise.all(held.map(route => route.abort().catch(() => {})));
  await choose('statementcontrol');
  assert.equal(await results.locator('[data-detector=D02][data-outcome=passed]').count(), 1);
  assert.equal(await results.locator('[data-outcome=flagged]').count(), 0);

  const heldOut = ['Bank statement', 'Account ID: QA-HOLDOUT', 'Period: 2026-02',
    'Number format: decimal comma', 'Currency: GBP', 'Beginning balance: (55,25)',
    'Money in: 104,30', 'Money out: 12,05', 'Ending balance: 37,00'];
  const paragraphs = heldOut.map(line => '<w:p><w:r><w:t>' + line + '</w:t></w:r></w:p>').join('');
  const xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' +
    paragraphs + '</w:body></w:document>';
  await picker.setInputFiles({name: 'held-out.docx', mimeType: 'application/octet-stream',
    buffer: Buffer.from(zipSync({'word/document.xml': strToU8(xml)}))});
  await upload.click();
  await ready.waitFor();
  assert.match(await results.locator('[data-detector=D02][data-outcome=passed]').innerText(), /37\.00 GBP/);
  const underdeclared = Buffer.from(zipSync({'word/document.xml': strToU8(xml)}, {level: 9}));
  const central = underdeclared.indexOf(Buffer.from([0x50, 0x4b, 0x01, 0x02]));
  assert.ok(central > 0);
  assert.equal(underdeclared.readUInt16LE(8), 8);
  underdeclared.writeUInt32LE(16, 22);
  underdeclared.writeUInt32LE(16, central + 24);
  await picker.setInputFiles({name: 'underdeclared.docx', mimeType: 'application/octet-stream', buffer: underdeclared});
  await upload.click();
  await page.getByRole('alert').getByText(/file could not be read/).waitFor();
  assert.equal(await results.innerText(), '');

  for (const width of [360, 390, 768, 1440]) {
    await page.setViewportSize({width, height: 850});
    await choose('purchase');
    const overflow = await page.evaluate(() => {
      const width = document.documentElement.clientWidth;
      return [...document.querySelectorAll('main *')].filter(node => node.getBoundingClientRect().right > width + 1)
        .map(node => node.localName + '.' + node.className).slice(0, 6);
    });
    assert.deepEqual(overflow, [], 'comparison overflow at ' + width);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
    for (const path of ['/capabilities.html', '/examples.html']) {
      await page.goto(origin + path);
      const cards = path.includes('capabilities') ? 12 : 8;
      await page.locator('.guide-cards article').last().waitFor();
      assert.equal(await page.locator('.guide-cards article').count(), cards);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
    }
    await page.goto(origin);
  }
  // 1280 CSS pixels at 200% browser zoom leaves a 640 CSS pixel layout width.
  await page.setViewportSize({width: 640, height: 450});
  await choose('statementgap');
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), 640);
  await page.screenshot({path: join(output, 'statement-reflow-640.png'), fullPage: true});
  await page.setViewportSize({width: 390, height: 844});
  await choose('purchase');
  await page.screenshot({path: join(output, 'comparison-390.png'), fullPage: true});
  // Verify actual browser-level network and storage boundaries for all review sessions.
  const localOrigin = new URL(origin).origin;
  assert.ok(book.every(([method, url, body]) => method === 'GET' && body === null &&
    new URL(url).origin === localOrigin && !new URL(url).search), JSON.stringify(book.filter(
    ([method, url, body]) => method !== 'GET' || body !== null || new URL(url).origin !== localOrigin || new URL(url).search)));
  assert.equal(await page.evaluate(async () => localStorage.length + sessionStorage.length +
    (await indexedDB.databases()).length + (await caches.keys()).length), 0);
  assert.deepEqual(errors, []);
  await page.setViewportSize({width: 1440, height: 900});
  await page.goto(origin);
  // Render the actual pages with the existing PDF.js runtime for visual inspection.
  const pdfNames = Object.keys(manifest.files).filter(name => name.endsWith('.pdf'));
  const rendered = await page.evaluate(async names => {
    const pdf = await import('/vendor/pdfjs/pdf.min.mjs');
    pdf.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/pdf.worker.min.mjs';
    const figures = document.createElement('div');
    figures.id = 'sample-pdf-qa';
    figures.style.display = 'grid';
    figures.style.gridTemplateColumns = 'repeat(3, minmax(0, 1fr))';
    document.body.replaceChildren(figures);
    let count = 0;
    for (const name of names) {
      const task = pdf.getDocument({url: '/samples/insights/' + name, isEvalSupported: false,
        useSystemFonts: true, useWasm: false});
      const doc = await task.promise;
      for (let index = 1; index <= doc.numPages; index++) {
        const page = await doc.getPage(index);
        const viewport = page.getViewport({scale: .65});
        const figure = document.createElement('figure');
        figure.style.margin = '8px';
        const title = document.createElement('figcaption');
        title.textContent = name + ' page ' + index;
        const canvas = document.createElement('canvas');
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        figure.append(title, canvas);
        figures.append(figure);
        await page.render({canvas, viewport}).promise;
        count++;
      }
      await task.destroy();
    }
    return count;
  }, pdfNames);
  assert.equal(rendered, 14);
  await page.locator('#sample-pdf-qa').screenshot({path: join(output, 'sample-pdf-pages.png')});
  console.log('PASS ' + resultChecks + ' typed sample assertions across ' + expected.length +
    ' scenarios, plus two invoice PDFs, manifest (' + Object.keys(manifest.files).length +
    ' files), held-out Word layout, understated ZIP rejection, source focus, local multi-file upload, cancellation, width reflow, guides, network and storage. Rendered ' + rendered + ' PDF pages.');
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
