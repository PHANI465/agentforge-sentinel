import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {join, resolve} from 'node:path';

const [origin, modules] = process.argv.slice(2);
const {chromium} = createRequire(join(resolve(modules), 'package.json'))('playwright');
const browser = await chromium.launch();
try {
  const context = await browser.newContext();
  const unrelated = await browser.newContext();
  const sameOrigin = {'sec-fetch-site': 'same-origin'};
  const entry = '/demo/session';
  assert.equal((await context.request.post(origin + entry)).status(), 403);
  const page = await context.newPage();
  page.setDefaultTimeout(45_000);
  await page.goto(origin + '/workbench');
  await page.getByRole('heading', {name: 'Try the analyst workbench'}).waitFor();
  const sessionResponse = page.waitForResponse(res => res.url() === origin + entry);
  await page.getByRole('button', {name: 'Start a demo case'}).click();
  const response = await sessionResponse;
  assert.equal(response.status(), 200);
  assert.match(response.headers()['cache-control'], /no-store/);
  const {token} = await response.json();
  const headers = {authorization: 'Bearer ' + token};
  const get = async path => {
    const value = await context.request.get(origin + path, {headers});
    assert.equal(value.status(), 200, path);
    return value.json();
  };

  const session = await get('/v1/session');
  assert.deepEqual(session.capabilities.toSorted(),
    ['approve_action','execute_simulated_action','read_case']);
  const initial = await get('/v1/overview');
  assert.equal(initial.transactions, 5);
  assert.equal(initial.alerts, 1);
  assert.equal(initial.simulated_actions, 0);
  assert.equal((await context.request.post(origin + '/v1/documents?format=pdf', {
    headers: {...headers, 'content-type':'application/pdf'}, data: '%PDF-1.4',
  })).status(), 403);
  const cases = await get('/v1/cases');
  assert.equal(cases.items.length, 1);
  const id = cases.items[0].id;
  const other = await unrelated.request.post(origin + entry, {headers:sameOrigin});
  assert.equal(other.status(), 200);
  assert.equal((await unrelated.request.get(origin + '/v1/cases/' + id, {
    headers:{authorization: 'Bearer ' + (await other.json()).token},
  })).status(), 404);
  assert.equal((await unrelated.request.get(origin + '/v1/cases/' + id)).status(), 401);

  const queueItem = page.getByRole('button', {name: /\bdemo-5\b/});
  await queueItem.click();
  await page.getByRole('button', {name:'Investigate case',exact:true}).click();
  await page.getByRole('button', {name:'Approve',exact:true}).waitFor();
  const trace = await get('/v1/cases/' + id + '/investigation-trace');
  assert.equal(trace.selected.workflow.status, 'completed');
  assert.equal(await page.getByRole('button', {name:/^Execute/}).count(), 0);
  assert.equal((await get('/v1/overview')).simulated_actions, 0);
  await page.getByRole('button', {name:'Approve',exact:true}).click();
  await page.getByRole('button', {name:'Execute simulated hold',exact:true}).waitFor();
  assert.equal((await get('/v1/overview')).simulated_actions, 0);

  const actionResponse = page.waitForResponse(res =>
    res.url() === origin + '/v1/actions' && res.request().method() === 'POST');
  await page.getByRole('button', {name:'Execute simulated hold',exact:true}).click();
  const executed = await actionResponse;
  assert.equal(executed.status(), 200);
  const first = await executed.json();
  assert.equal(first.replayed, false);
  assert.equal(first.action.state, 'succeeded');
  const retry = await context.request.post(origin + '/v1/actions', {
    headers, data: executed.request().postDataJSON(),
  });
  assert.equal(retry.status(), 200);
  const replay = await retry.json();
  assert.equal(replay.replayed, true);
  assert.equal(replay.action.id, first.action.id);
  assert.equal((await get('/v1/overview')).simulated_actions, 1);
  assert.equal((await get('/v1/cases/' + id)).case.state, 'closed');
  await page.getByRole('button', {name:'Sign out'}).click();
  await page.getByRole('heading', {name:'Try the analyst workbench'}).waitFor();
  assert.equal(await page.evaluate(() => localStorage.length + sessionStorage.length), 0);
  console.log('Hosted browser smoke passed: private seeded case, isolated sessions, denied document upload, investigation, approval, one simulated action, idempotent replay and sign-out.');
} finally {
  await browser.close();
}
