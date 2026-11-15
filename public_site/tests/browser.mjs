import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {extname, join, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const [modules, fixtures, artifacts, target, invoiceFixtures] = process.argv.slice(2);
const hosted = target === '--local' ? undefined : target;
const {chromium} = createRequire(join(resolve(modules), 'package.json'))('playwright');
const root = fileURLToPath(new URL('../static/', import.meta.url));
const contentType = {'.html':'text/html', '.css':'text/css', '.mjs':'text/javascript', '.js':'text/javascript', '.svg':'image/svg+xml', '.pdf':'application/pdf', '.json':'application/json', '.woff2':'font/woff2'};
const server = createServer(async (request, response) => {
  const pathname = new URL(request.url, 'http://localhost').pathname;
  const path = resolve(root, '.' + (pathname === '/' ? '/index.html' : pathname));
  if (!path.startsWith(resolve(root) + sep)) {
    response.writeHead(404).end();
    return;
  }
  try {
    const bytes = await readFile(path);
    response.writeHead(200, {'Content-Type':contentType[extname(path)] ?? 'application/octet-stream'}).end(bytes);
  } catch {
    response.writeHead(404).end();
  }
});
if (!hosted) await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = hosted ?? `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch();
try {
  const page = await browser.newPage({viewport:{width:1440,height:900}, reducedMotion:'reduce'});
  const errors = [];
  const writes = [];
  const requests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    if (request.method() !== 'GET') writes.push(request.method());
    requests.push(request.url());
  });
  await page.goto(origin);
  await page.getByRole('heading', {name:'Understand what your financial PDF says'}).waitFor();
  await page.screenshot({path:join(artifacts,'desktop.png'),fullPage:true});
  await page.getByRole('button', {name:'Try the sample'}).click();
  await page.getByText('Readable text on 2 of 2 pages.').waitFor();
  const closing = page.getByRole('listitem').filter({has:page.getByRole('heading',{name:'Closing balance',exact:true})});
  assert.equal(await closing.getByText('USD 1,554.90',{exact:true}).count(), 1);
  assert.equal(await closing.getByText('Source page 2',{exact:true}).count(), 1);
  await page.screenshot({path:join(artifacts,'sample.png'),fullPage:true});
  await page.getByRole('button', {name:'Clear',exact:true}).click();
  assert.equal(await page.locator('#results').innerText(), '');
  const picker = page.locator('#pdf-file');
  await picker.setInputFiles(join(fixtures,'pdf_text_statement.pdf'));
  const before = requests.length;
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByText('PDF reviewed in this browser.').waitFor();
  assert.equal(await closing.getByText('USD 1,554.90',{exact:true}).count(), 1);
  assert.ok(requests.slice(before).every(url => url.startsWith(origin + '/vendor/pdfjs/')), requests.slice(before).join(', '));
  await picker.setInputFiles(join(fixtures,'pdf_image_only.pdf'));
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByRole('heading', {name:'No readable text found'}).waitFor();
  await picker.setInputFiles(join(fixtures,'pdf_scanned_mixed.pdf'));
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByText('Readable text on 1 of 2 pages.').waitFor();
  await picker.setInputFiles(join(fixtures,'pdf_hostile_text.pdf'));
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByText('PDF reviewed in this browser.').waitFor();
  await page.getByText('Read page excerpts', {exact:true}).click();
  assert.equal(await page.locator('#results img, #results iframe, #results a, #results script').count(), 0);
  assert.match(await page.locator('#results').innerText(), /ignore|override|script/i);
  await picker.setInputFiles({name:'fake.pdf',mimeType:'application/pdf',buffer:Buffer.from('this is not a PDF')});
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByRole('alert').getByText(/does not have a PDF header/).waitFor();
  await picker.setInputFiles({name:'large.pdf',mimeType:'application/pdf',buffer:Buffer.alloc(10_000_001)});
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByRole('alert').getByText(/exceeds 10 MB/).waitFor();
  await picker.setInputFiles(join(fixtures,'pdf_encrypted.pdf'));
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByRole('alert').getByText(/could not be read/i).waitFor();

  if (invoiceFixtures) {
    const samples = [
      ['QA_Test_01_Math_Discrepancy.pdf', ['line-math','subtotal-math','total-math'], ['$480.00','$680.00','$1,280.00','$1,480.00','$1,598.40','$1,898.40']],
      ['QA_Test_02_Threshold_Splitting.pdf', ['approval-limit','address-overlap'], ['$4,995.00','$5.00','$5,000.00','$9,990.00']],
      ['QA_Test_03_Remittance_Mismatch.pdf', ['payment-change','payee-name','routing-format','email-verify'], ['all zeros','Beneficiary name differs from the vendor']],
    ];
    for (const [filename, codes, facts] of samples) {
      await picker.setInputFiles(join(invoiceFixtures,filename));
      const selected = requests.length;
      await page.getByRole('button', {name:'Explain this PDF'}).click();
      await page.getByText('PDF reviewed in this browser.').waitFor();
      assert.deepEqual(await page.locator('#results [data-check]').evaluateAll(nodes => nodes.map(node => node.dataset.check)),codes);
      const copy = await page.locator('#results .checks').innerText();
      for (const fact of facts) assert.ok(copy.includes(fact), filename + ' missing ' + fact);
      assert.ok(!copy.includes('Expected flags:') && !copy.includes('Expected anomalies:'));
      assert.ok(requests.slice(selected).every(url => url.startsWith(origin + '/vendor/pdfjs/')));
    }
  }
  const narrow = await browser.newPage({viewport:{width:390,height:844}});
  await narrow.goto(origin);
  await narrow.keyboard.press('Tab');
  assert.equal(await narrow.evaluate(()=>document.activeElement.textContent),'Skip to content');
  await narrow.getByRole('link',{name:'Explain a PDF'}).first().click();
  assert.equal(await narrow.evaluate(()=>document.documentElement.scrollWidth),390);
  await narrow.screenshot({path:join(artifacts,'mobile.png'),fullPage:true});
  await page.getByRole('link',{name:/Walk through the recorded case/}).click();

  await page.getByRole('heading',{name:'Follow one fraud case'}).waitFor();
  await page.getByRole('heading',{name:'A large debit triggers an alert'}).waitFor();
  await page.screenshot({path:join(artifacts,'walkthrough-desktop.png'),fullPage:true});
  const phases = [
    'Investigators check the activity behind the alert',
    'The proposal waits for a decision',
    'The approved action runs in the simulator',
    'The audit explains how the case closed',
  ];
  for (const title of phases) {
    await page.getByRole('button',{name:'Next',exact:true}).click();
    await page.getByRole('heading',{name:title}).waitFor();
    assert.equal(await page.evaluate(()=>document.activeElement.id),'walk-title');
  }
  assert.equal(await page.locator('[aria-current=step]').count(),1);
  await narrow.goto(origin + '/walkthrough.html');
  await narrow.getByRole('heading',{name:'A large debit triggers an alert'}).waitFor();
  assert.equal(await narrow.evaluate(()=>document.documentElement.scrollWidth),390);
  await narrow.screenshot({path:join(artifacts,'walkthrough-mobile.png'),fullPage:true});
  await page.getByRole('link',{name:/technical replay/}).click();
  await page.getByRole('heading',{name:'Recorded replay of one synthetic case'}).waitFor();
  await page.getByRole('button',{name:/^Next/}).click();
  await page.getByRole('link',{name:'Back to the case overview'}).click();
  await page.getByRole('link',{name:'Back to Sentinel'}).click();
  await page.getByRole('heading',{name:'Understand what your financial PDF says'}).waitFor();
  assert.deepEqual(errors,[]);
  assert.deepEqual(writes,[]);
  console.log('Passed sample and local PDF, image only and mixed PDF, inert text, bad header, size and password rejection, clear, GET-only traffic, keyboard, 390 px layouts and both replay views.');
  if (invoiceFixtures) console.log('All three invoice PDFs produced their expected distinct findings and values.');
} finally {
  await browser.close();
  if (server.listening) await new Promise(resolve => server.close(resolve));
}
