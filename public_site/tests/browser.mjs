import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {extname, join, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

import {strToU8, zipSync} from '../static/vendor/fflate.mjs';

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
  await page.getByRole('heading', {name:'Understand your financial documents'}).waitFor();
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
  await page.getByRole('button', {name:'Review this file'}).click();
  await page.getByText('PDF reviewed in this browser.').waitFor();
  assert.equal(await closing.getByText('USD 1,554.90',{exact:true}).count(), 1);
  assert.ok(requests.slice(before).every(url => url.startsWith(origin + '/vendor/pdfjs/')), requests.slice(before).join(', '));
  await picker.setInputFiles(join(fixtures,'pdf_image_only.pdf'));
  await page.getByRole('button', {name:'Review this file'}).click();
  await page.getByRole('heading', {name:'No readable text found'}).waitFor();
  await picker.setInputFiles(join(fixtures,'pdf_scanned_mixed.pdf'));
  await page.getByRole('button', {name:'Review this file'}).click();
  await page.getByText('Readable text on 1 of 2 pages.').waitFor();
  await picker.setInputFiles(join(fixtures,'pdf_hostile_text.pdf'));
  await page.getByRole('button', {name:'Review this file'}).click();
  await page.getByText('PDF reviewed in this browser.').waitFor();
  await page.getByText('Read page excerpts', {exact:true}).click();
  assert.equal(await page.locator('#results img, #results iframe, #results a, #results script').count(), 0);
  assert.match(await page.locator('#results').innerText(), /ignore|override|script/i);
  await picker.setInputFiles({name:'fake.pdf',mimeType:'application/pdf',buffer:Buffer.from('this is not a PDF')});
  await page.getByRole('button', {name:'Review this file'}).click();
  await page.getByRole('alert').getByText(/does not have a PDF header/).waitFor();
  await picker.setInputFiles({name:'large.pdf',mimeType:'application/pdf',buffer:Buffer.alloc(10_000_001)});
  await page.getByRole('button', {name:'Review this file'}).click();
  await page.getByRole('alert').getByText(/exceeds 10 MB/).waitFor();
  await picker.setInputFiles(join(fixtures,'pdf_encrypted.pdf'));
  await page.getByRole('button', {name:'Review this file'}).click();
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
      await page.getByRole('button', {name:'Review this file'}).click();
      await page.getByText('PDF reviewed in this browser.').waitFor();
      assert.deepEqual(await page.locator('#results [data-check]').evaluateAll(nodes => nodes.map(node => node.dataset.check)),codes);
      const copy = await page.locator('#results .checks').innerText();
      for (const fact of facts) assert.ok(copy.includes(fact), filename + ' missing ' + fact);
      assert.ok(!copy.includes('Expected flags:') && !copy.includes('Expected anomalies:'));
      assert.ok(requests.slice(selected).every(url => url.startsWith(origin + '/vendor/pdfjs/')));
    }
  }
  for (const [sampleName, month, receipts, outlays, deficit] of [
    ['january','January','513,294','641,935','128,640'],
    ['may','May','371,229','687,233','316,004'],
  ]) {
    await page.getByLabel('Sample document').selectOption(sampleName);
    await page.getByRole('button',{name:'Try the sample'}).click();
    await page.getByText('Public Treasury sample reviewed.').waitFor();
    const chart = page.locator('.review-chart').filter({hasText:month + ' 2025 budget summary'});
    const text = await chart.innerText();
    assert.ok([receipts, outlays, deficit, 'Source page 5, Table 2'].every(value => text.includes(value)));
    assert.equal(await chart.locator('meter').count(),2);
  }
  const workbookParts = {
    'xl/workbook.xml':'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Ledger" r:id="rId1"/></sheets></workbook>',
    'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="/xl/worksheets/sheet1.xml"/></Relationships>',
    'xl/worksheets/sheet1.xml':'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Currency</t></is></c><c r="B1" t="inlineStr"><is><t>Amount</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>USD</t></is></c><c r="B2"><v>150</v></c></row><row r="3"><c r="A3" t="inlineStr"><is><t>USD</t></is></c><c r="B3"><v>-25.50</v></c></row><row r="4"><c r="A4" t="inlineStr"><is><t>EUR</t></is></c><c r="B4"><v>11.25</v></c></row><row r="5"><c r="A5" t="inlineStr"><is><t>USD</t></is></c><c r="B5"><f>75*100</f><v>7500</v></c></row></sheetData></worksheet>',
  };
  const wordParts = {
    'word/document.xml':'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Invoice Example 7</w:t></w:r></w:p><w:p><w:r><w:t>Total Due: $42.00</w:t></w:r></w:p></w:body></w:document>',
  };
  const zip = parts => Buffer.from(zipSync(Object.fromEntries(Object.entries(parts).map(([name,text]) => [name,strToU8(text)]))));
  await picker.setInputFiles({name:'ledger.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:zip(workbookParts)});
  await page.getByRole('button',{name:'Review this file'}).click();
  await page.getByRole('heading',{name:'Excel workbook'}).waitFor();
  assert.match(await page.locator('#results').innerText(), /3 data rows counted/);
  assert.match(await page.locator('#results').innerText(), /124\.50 USD/);
  assert.match(await page.locator('#results').innerText(), /11\.25 EUR/);
  assert.doesNotMatch(await page.locator('#results').innerText(), /7500/);
  await picker.setInputFiles({name:'invoice.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:zip(wordParts)});
  await page.getByRole('button',{name:'Review this file'}).click();
  await page.getByRole('heading',{name:'Invoice in Word'}).waitFor();
  await page.getByText('$42.00',{exact:true}).waitFor();
  await page.getByText('Source document body',{exact:true}).waitFor();
  await picker.setInputFiles({name:'legacy.doc',mimeType:'application/msword',buffer:Buffer.from('legacy')});
  await page.getByRole('button',{name:'Review this file'}).click();
  await page.getByRole('alert').getByText(/Save an older Word DOC file/).waitFor();
  const narrow = await browser.newPage({viewport:{width:390,height:844}});
  await narrow.goto(origin);
  await narrow.keyboard.press('Tab');
  assert.equal(await narrow.evaluate(()=>document.activeElement.textContent),'Skip to content');
  await narrow.getByRole('link',{name:'Review a document'}).first().click();
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
  await page.getByRole('link',{name:'Follow all 10 steps'}).click();
  await page.getByRole('heading',{name:'Follow the case from alert to audit'}).waitFor();
  const detailed = [
    'A large debit triggers an alert',
    'The alert becomes a case',
    'The evidence analyst gathers the facts',
    'The investigator proposes a simulated hold',
    'The reviewer accepts the evidence',
    'Sentinel prepares the exact action for approval',
    'The approval is recorded',
    'The simulated hold runs once',
    'A retry returns the same action',
    'The audit explains how the case closed',
  ];
  for (const [index, title] of detailed.entries()) {
    await page.getByRole('heading',{name:title,exact:true}).waitFor();
    assert.equal(await page.locator('.diagram-nodes li').count(),3);
    assert.equal(await page.locator('.rail-btn[aria-current=step]').getAttribute('data-index'),String(index));
    const snapshot = await page.locator('#ledger .kv-row dd').allTextContents();
    assert.equal(snapshot[1],index < 6 ? '0' : '1');
    assert.equal(snapshot[2],index < 7 ? '0' : '1');
    assert.equal(await page.locator('#records').getAttribute('open'),null);
    const snapshotNote = await page.locator('#snapshot-note').innerText();
    assert.equal(snapshotNote.includes('Steps 3–6 share this snapshot.'),index >= 2 && index <= 5);
    if (index === 0) await page.screenshot({path:join(artifacts,'detailed-desktop.png')});
    if (index < detailed.length - 1) {
      await page.getByRole('button',{name:/^Next/}).click();
      assert.equal(await page.evaluate(()=>document.activeElement.id),'frame-title');
    }
  }
  assert.equal(await page.getByRole('button',{name:/^Next/}).isDisabled(),true);
  await page.getByRole('button',{name:/Open the case/}).click();
  await page.locator('#records > summary').click();
  await page.locator('#frame-body a[href^="#rec-"]').first().click();
  assert.equal(await page.locator('#frame-title').innerText(),detailed[0]);
  assert.equal(await page.locator('#records').evaluate(node=>node.open),true);
  assert.match(await page.evaluate(()=>document.activeElement.id),/^rec-/);

  await narrow.goto(origin + '/walkthrough-details.html#frame-7');
  await narrow.getByRole('heading',{name:detailed[6],exact:true}).waitFor();
  await narrow.screenshot({path:join(artifacts,'detailed-mobile.png'),fullPage:true});
  for (const [index,title] of detailed.entries()) {
    await narrow.getByLabel('Jump to a step').selectOption(String(index));
    await narrow.getByRole('heading',{name:title,exact:true}).waitFor();
    await narrow.locator('#records > summary').click();
    assert.equal(await narrow.evaluate(()=>document.documentElement.scrollWidth),390);
  }
  await narrow.goto(origin + '/dataset.html');
  assert.equal(await narrow.locator('.dataset-steps li').count(),3);
  assert.equal(await narrow.evaluate(()=>document.documentElement.scrollWidth),390);
  await page.getByRole('navigation',{name:'Site navigation'}).getByRole('link',{name:'Case overview'}).click();
  await page.getByRole('link',{name:'Back to Sentinel'}).click();
  await page.getByRole('heading',{name:'Understand your financial documents'}).waitFor();
  assert.deepEqual(errors,[]);
  assert.deepEqual(writes,[]);
  console.log('Passed sample and local PDF, image only and mixed PDF, inert text, bad header, size and password rejection, clear, GET-only traffic, keyboard, 390 px layouts, all 10 detailed steps, shared snapshots, cross-step record links and both replay views, two original Treasury PDFs, workbook metrics and Word review.');
  if (invoiceFixtures) console.log('All three invoice PDFs produced their expected distinct findings and values.');
} finally {
  await browser.close();
  if (server.listening) await new Promise(resolve => server.close(resolve));
}
