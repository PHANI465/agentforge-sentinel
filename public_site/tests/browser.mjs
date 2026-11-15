import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {extname, join, resolve, sep} from 'node:path';
import {fileURLToPath} from 'node:url';

const [modules, fixtures, artifacts, hosted] = process.argv.slice(2);
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
  await picker.setInputFiles({name:'large.pdf',mimeType:'application/pdf',buffer:Buffer.alloc(10*1024*1024+1)});
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByRole('alert').getByText(/exceeds 10 MiB/).waitFor();
  await picker.setInputFiles(join(fixtures,'pdf_encrypted.pdf'));
  await page.getByRole('button', {name:'Explain this PDF'}).click();
  await page.getByRole('alert').getByText(/could not be read/i).waitFor();
  const narrow = await browser.newPage({viewport:{width:390,height:844}});
  await narrow.goto(origin);
  await narrow.keyboard.press('Tab');
  assert.equal(await narrow.evaluate(()=>document.activeElement.textContent),'Skip to content');
  await narrow.getByRole('link',{name:'Explain a PDF'}).first().click();
  assert.equal(await narrow.evaluate(()=>document.documentElement.scrollWidth),390);
  await narrow.screenshot({path:join(artifacts,'mobile.png'),fullPage:true});
  await page.getByRole('link',{name:/Walk through the recorded case/}).click();
  await page.getByRole('heading',{name:'Recorded replay of one synthetic case'}).waitFor();
  await page.getByRole('button',{name:/^Next/}).click();
  await page.getByRole('link',{name:'Back to Sentinel'}).click();
  await page.getByRole('heading',{name:'Understand what your financial PDF says'}).waitFor();
  assert.deepEqual(errors,[]);
  assert.deepEqual(writes,[]);
  console.log('Passed sample and local PDF, image only and mixed PDF, inert text, bad header, size and password rejection, clear, GET-only traffic, keyboard, 390 px layout and replay navigation.');
} finally {
  await browser.close();
  if (server.listening) await new Promise(resolve => server.close(resolve));
}
