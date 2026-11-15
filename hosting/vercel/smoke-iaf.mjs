import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {join, resolve} from 'node:path';

const [origin, modules] = process.argv.slice(2);
const {chromium} = createRequire(join(resolve(modules), 'package.json'))('playwright');
const browser = await chromium.launch();
try {
  const page = await browser.newPage({viewport:{width:390,height:844}});
  await page.goto(origin + '/iaf.html');
  await page.getByRole('heading',{name:'IAF',exact:true}).waitFor();
  await page.getByRole('button',{name:'What makes Sentinel different?'}).click();
  let answer = page.locator('.iaf-message.assistant').last();
  await answer.getByText(/links findings to source pages/i).waitFor();
  assert.equal(await answer.getByRole('link').getAttribute('href'),origin + '/');
  await page.getByRole('button',{name:'Who built Sentinel?'}).click();
  answer = page.locator('.iaf-message.assistant').last();
  await answer.getByText(/Arizona State University/).waitFor();
  assert.equal(await answer.getByRole('link').getAttribute('href'),'https://phaneendragavara.dev/');
  await page.getByLabel('Ask a question').fill('What is the capital of Japan?');
  await page.getByRole('button',{name:'Ask IAF',exact:true}).click();
  await page.getByText('I can explain Sentinel and its public project author.',{exact:false}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),390);
  assert.equal((await page.request.post(origin + '/iaf/ask', {
    data:{question:'sentinel'},
  })).status(),403);
  console.log('IAF source citations, author scope, unrelated-question refusal, 390 px layout and cross-site request rejection passed.');
} finally {
  await browser.close();
}
