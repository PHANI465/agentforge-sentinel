import {comparison, metricList, renderWorkbook} from './review-charts.mjs';
import {readDocument, readSample, reviewWorker, ReviewError, validateFiles} from './review-input.mjs';
import {samples} from './insight-samples.mjs';
import {renderChecks, renderPacket} from './insights-view.mjs';
import {evidenceLimits} from './document-evidence.mjs';

const sampleOptions = document.querySelector('#sample-choice');
const fileInput = document.querySelector('#pdf-file');
const analyze = document.querySelector('#analyze');
const sample = document.querySelector('#sample');
const clear = document.querySelector('#clear');
const status = document.querySelector('#status');
const error = document.querySelector('#error');
const loading = document.querySelector('#loading');
const results = document.querySelector('#results');
const trusted = document.querySelector('#trusted-document');
const policy = document.querySelector('#policy-limit');
const currency = document.querySelector('#policy-currency');
const days = document.querySelector('#policy-days');
const options = document.querySelector('#comparison-options');
let generation = 0;
let active;
let busy = false;

for (const [key, item] of Object.entries(samples)) sampleOptions.add(new Option(item.title, key));
const requestedSample = new URLSearchParams(location.search).get('sample');
if (Object.hasOwn(samples, requestedSample)) sampleOptions.value = requestedSample;

function make(tag, style, copy) {
  const element = document.createElement(tag);
  if (style) element.className = style;
  if (copy) element.textContent = copy;
  return element;
}

function renderLegacy(report, total, {word, summary} = {}) {
  const output = make('section', 'results');
  const location = page => word ? 'document body' : 'page ' + page;
  const title = summary ? 'Treasury budget statement' : word
    ? (report.kind === 'PDF text review' ? 'Word document' : report.kind + ' in Word')
    : report.kind;
  const heading = make('h3', 'heading-5', report.readable ? title : 'No readable text found');
  heading.tabIndex = -1;
  output.append(heading);
  output.append(make('p', 'body-3', `Readable text on ${report.readable} of ${total} pages.`));
  if (word) {
    output.lastElementChild.textContent = 'Review of text and tables in the document body.';
    output.append(metricList([
      {label:'Paragraphs',text:String(word.paragraphs)},
      {label:'Tables',text:String(word.tables)},
    ]));
  }
  if (summary) output.append(comparison(summary));
  if (report.missing.length && !word) {
    output.append(make('p', 'body-3', `No readable text on ${report.missing.length === 1 ? 'page' : 'pages'} ${report.missing.join(', ')}. If these pages are scans, use a copy with selectable text.`));
  }
  if (report.readable) {
    if (report.invoiceCoverage?.rows) {
      output.append(metricList([
        {label: 'Invoice rows checked', text: String(report.invoiceCoverage.rows)},
        {label: 'Subtotals compared', text: String(report.invoiceCoverage.subtotals)},
        {label: 'Payable totals compared', text: String(report.invoiceCoverage.payable)},
      ]));
    }
    if (report.checks.length) {
      output.append(make('h4', 'heading-6', 'What to review'));
      const checks = make('ol', 'checks');
      for (const check of report.checks) {
        const item = make('li');
        item.dataset.check = check.code;
        item.append(make('h5', 'title-3', check.title));
        if (check.item) item.append(make('p', 'body-6', check.item));
        item.append(make('p', 'body-3', check.description));
        if (check.comparison) item.append(comparison({
          title:'Calculated and printed amounts', note:'Source ' + location(check.page) + '.',
          ...check.comparison,
        }));
        const evidence = make('details');
        evidence.append(make('summary', 'title-4', (word ? 'Evidence in ' : 'Evidence on ') + location(check.page)),
          make('p', 'body-6', check.line));
        item.append(evidence);
        checks.append(item);
      }
      output.append(checks);
    } else if (report.kind === 'Invoice') {
      output.append(make('p', 'body-3', 'No flags from the recognized invoice patterns. See the capability guide for required fields and layouts.'));
    }
    if (report.findings.length) {
      output.append(make('h4', 'heading-6', 'Amounts and terms found'));
      const cards = make('ul', 'findings');
      for (const finding of report.findings) {
        const item = make('li');
        item.append(make('h4', 'title-3', finding.title));
        if (finding.amount) item.append(make('p', 'heading-5', finding.amount));
        item.append(
          make('p', 'body-6', finding.description),
          make('blockquote', 'body-6', finding.line.slice(0, 300)),
          make('span', 'caption-2', 'Source ' + location(finding.page)),
        );
        cards.append(item);
      }
      output.append(cards);
    } else {
      if (!summary && !report.checks.length) output.append(make('p', 'body-3', 'No supported labeled amounts or terms were found. Use the excerpts below to review the extracted text.'));
    }
    output.append(make('p', 'caption-2', 'Sentinel quotes printed amounts and checks recognizable invoice rows. Compare each finding with the source. A flag is a reason to review.'));
    const excerpts = make('details');
    excerpts.append(make('summary', 'title-3', word ? 'Read document excerpts' : 'Read page excerpts'));
    for (const excerpt of report.excerpts) {
      excerpts.append(make('p', 'title-4', word ? 'Document body' : 'Page ' + excerpt.page), make('p', 'excerpt body-6', excerpt.text));
    }
    output.append(excerpts);
  }
  return output;
}

function controls() {
  analyze.disabled = busy || !fileInput.files.length;
  sample.disabled = busy;
  sampleOptions.disabled = busy;
  loading.hidden = !busy;
}

function reset(message) {
  generation += 1;
  active?.abort();
  active = undefined;
  results.replaceChildren();
  error.hidden = true;
  error.textContent = '';
  status.textContent = message;
  busy = false;
  clear.textContent = 'Clear';
  clear.hidden = !fileInput.files.length;
  controls();
}

function refreshSelection() {
  trusted.replaceChildren(new Option('None selected', ''));
  for (let index = 1; index <= Math.min(fileInput.files.length, 10); index++) {
    trusted.add(new Option('Document ' + index + ' (' + fileInput.files[index - 1].name + ')', 'doc_' + index));
  }
  options.hidden = fileInput.files.length < 2;
  analyze.textContent = fileInput.files.length > 1 ? 'Compare these files' : 'Review this file';
}

function showAll(parsed, report) {
  const fragment = document.createDocumentFragment();
  if (parsed.length > 1) {
    const heading = make('h3', 'heading-5', 'Document comparison');
    fragment.append(heading, renderPacket(report.documents),
      renderChecks(report.comparisons, parsed, 'Comparison findings'));
  }
  for (const [index, original] of parsed.entries()) {
    const result = report.documents[index];
    if (original.descriptor.sha256 !== result.descriptor.sha256 || original.descriptor.id !== result.descriptor.id) {
      throw new ReviewError('The results no longer match the selected documents.');
    }
    const view = original.workbook ? renderWorkbook(original.workbook) :
      renderLegacy(result.report, original.pages.length, {word: original.word, summary: result.summary});
    if (result.checks.length) view.prepend(renderChecks(result.checks, parsed, 'Statement checks'));
    if (parsed.length > 1) {
      const details = make('details', 'document-preview');
      const name = view.querySelector('h3').textContent;
      details.append(make('summary', 'title-3', 'Document ' + (index + 1) + ' · ' + name), view);
      fragment.append(details);
    } else fragment.append(view);
  }
  results.replaceChildren(fragment);
  const first = results.querySelector('h3');
  first.tabIndex = -1;
  first.focus();
}

async function review(useSample) {
  const selectedSample = useSample ? samples[sampleOptions.value] : undefined;
  if (useSample) {
    fileInput.value = '';
    refreshSelection();
  }
  reset('Reading your documents?');
  const current = generation;
  const controller = new AbortController();
  const {signal} = controller;
  active = controller;
  const settings = {trusted: selectedSample?.trusted ?? trusted.value,
    policy: selectedSample ? selectedSample.policy :
      policy.value ? {currency: currency.value, limit: policy.value, days: Number(days.value)} : undefined,
    reviewId: 'r_' + crypto.randomUUID()};
  busy = true;
  clear.hidden = false;
  clear.textContent = 'Cancel';
  controls();
  let worker;
  const timeout = setTimeout(() => controller.abort(new ReviewError('The review took too long. Try fewer or shorter documents.')), 25_000);
  try {
    const files = selectedSample ? [] : validateFiles([...fileInput.files]);
    if (selectedSample) {
      let budget = evidenceLimits.totalBytes;
      for (const path of selectedSample.files) {
        const item = await readSample(path, path.split('.').at(-1), signal, budget);
        budget -= item.file.size;
        files.push(item);
      }
    }
    signal.throwIfAborted();
    worker = reviewWorker(signal);
    const parsed = [];
    for (const [index, item] of files.entries()) {
      status.textContent = 'Reading document ' + (index + 1) + ' of ' + files.length + '?';
      parsed.push(await readDocument(item, 'doc_' + (index + 1), signal, worker, (page, total) => {
        if (current === generation && !signal.aborted) status.textContent =
          'Document ' + (index + 1) + ' ? Page ' + page + ' of ' + total;
      }));
      signal.throwIfAborted();
    }
    const report = await worker.run({type: 'analyze', documents: parsed, options: settings});
    if (generation !== current || signal.aborted) return;
    showAll(parsed, report);
    status.textContent = selectedSample ? (selectedSample.official ? 'Public Treasury sample reviewed.' : 'Synthetic sample reviewed.') :
      files.length === 1 && files[0].format === 'pdf' ? 'PDF reviewed in this browser.' : 'Document reviewed in this browser.';
  } catch (failure) {
    if (generation !== current) return;
    error.textContent = failure instanceof ReviewError ? failure.message :
      'This file could not be read. Choose an intact text PDF, XLSX or DOCX without a password.';
    error.hidden = false;
    error.tabIndex = -1;
    error.focus();
    status.textContent = 'Review could not finish.';
  } finally {
    clearTimeout(timeout);
    worker?.close();
    if (generation === current) {
      active = undefined;
      busy = false;
      clear.textContent = 'Clear';
      controls();
    }
  }
}

fileInput.addEventListener('change', () => {
  refreshSelection();
  reset(fileInput.files.length ? 'Documents ready to review.' : 'Choose a file or try a sample.');
});
for (const setting of [trusted, currency, sampleOptions]) {
  setting.addEventListener('change', () => reset('Selection changed. Start a new review.'));
}
for (const setting of [policy, days]) {
  setting.addEventListener('input', () => reset('Policy changed. Start a new review.'));
}
analyze.addEventListener('click', () => { void review(false); });
sample.addEventListener('click', () => { void review(true); });
clear.addEventListener('click', () => {
  const canceled = busy;
  fileInput.value = '';
  policy.value = '';
  currency.value = 'USD';
  days.value = '7';
  refreshSelection();
  reset(canceled ? 'Review canceled.' : 'Choose a file or try a sample.');
  fileInput.focus();
});
