import {explain, maximumBytes, maximumCharacters, maximumPages, pageLines} from './pdf-review.mjs';

import {treasurySummary} from './financial-metrics.mjs';
import {comparison, metricList, renderWorkbook} from './review-charts.mjs';
import {readOpenXml} from './openxml-review.mjs';

const sampleOptions = document.querySelector('#sample-choice');
const pdfSamples = {
  statement: 'sample-statement.pdf',
  january: 'samples/treasury-jan-2025.pdf',
  may: 'samples/treasury-may-2025.pdf',
};
const fileInput = document.querySelector('#pdf-file');
const analyze = document.querySelector('#analyze');
const sample = document.querySelector('#sample');
const clear = document.querySelector('#clear');
const status = document.querySelector('#status');
const error = document.querySelector('#error');
const loading = document.querySelector('#loading');
const results = document.querySelector('#results');
let generation = 0;
let activeTask;
let sampleRequest;
let busy = false;

class ReviewError extends Error {}

function make(tag, style, copy) {
  const element = document.createElement(tag);
  if (style) element.className = style;
  if (copy) element.textContent = copy;
  return element;
}

function controls() {
  analyze.disabled = busy || !fileInput.files.length;
  sample.disabled = busy;
  sampleOptions.disabled = busy;
  loading.hidden = !busy;
}

function reset(message) {
  generation += 1;
  sampleRequest?.abort();
  sampleRequest = undefined;
  if (activeTask) void activeTask.destroy().catch(() => {});
  activeTask = undefined;
  results.replaceChildren();
  error.hidden = true;
  error.textContent = '';
  status.textContent = message;
  busy = false;
  clear.hidden = !fileInput.files.length;
  controls();
}

function show(report, total, {word, summary} = {}) {
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
      output.append(make('p', 'body-3', 'No review flags from the invoice checks that could run. Check the source for any amounts, terms or layouts this review did not cover.'));
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
  results.replaceChildren(output);
  heading.focus();
}

async function review(useSample) {
  const file = fileInput.files[0];
  if (!useSample && !file) return;
  if (useSample) fileInput.value = '';
  reset('Reading your document…');
  const current = generation;
  const selectedSample = sampleOptions.value;
  busy = true;
  clear.hidden = false;
  controls();
  let task;
  const timeout = setTimeout(() => {
    if (generation !== current) return;
    reset('Review stopped.');
    error.textContent = 'The file took too long to read. Try a shorter document.';
    error.hidden = false;
    clear.hidden = false;
  }, 25_000);
  try {
    let bytes;
    const format = useSample ? 'pdf' : file.name.split('.').at(-1).toLowerCase();
    if (!['pdf','xlsx','docx'].includes(format)) {
      throw new ReviewError('Choose PDF, XLSX or DOCX. Save an older Word DOC file as DOCX first.');
    }
    if (useSample) {
      sampleRequest = new AbortController();
      const response = await fetch(new URL(pdfSamples[selectedSample], import.meta.url), {signal: sampleRequest.signal});
      if (!response.ok) throw new ReviewError('The sample could not load. Try again or choose a PDF.');
      bytes = await response.arrayBuffer();
    } else {
      if (file.size > maximumBytes) throw new ReviewError('This file exceeds 10 MB. Choose a smaller document.');
      bytes = await file.arrayBuffer();
    }
    if (current !== generation) return;
    if (format !== 'pdf') {
      const structured = readOpenXml(new Uint8Array(bytes), format);
      if (format === 'xlsx') {
        const output = renderWorkbook(structured);
        results.replaceChildren(output);
        output.querySelector('h3').focus();
      } else {
        const count = structured.lines.reduce((sum,line) => sum + line.length,0);
        if (count > maximumCharacters) throw new ReviewError('This document has too much text for one review.');
        show(explain([{number:1,lines:structured.lines}]), 1, {word:structured});
      }
      status.textContent = 'Document reviewed in this browser.';
      return;
    }
    if (!new TextDecoder().decode(bytes.slice(0, 1024)).includes('%PDF-')) {
      throw new ReviewError('This file does not have a PDF header. Choose a PDF file.');
    }
    const pdf = await import('./vendor/pdfjs/pdf.min.mjs');
    if (current !== generation) return;
    pdf.GlobalWorkerOptions.workerSrc = new URL('./vendor/pdfjs/pdf.worker.min.mjs', import.meta.url).href;
    task = pdf.getDocument({
      data: new Uint8Array(bytes),
      isEvalSupported: false,
      disableFontFace: true,
      useSystemFonts: false,
      useWasm: false,
      stopAtErrors: true,
      cMapUrl: new URL('./vendor/pdfjs/cmaps/', import.meta.url).href,
      cMapPacked: true,
    });
    activeTask = task;
    task.onPassword = () => { void task.destroy().catch(() => {}); };
    const documentPdf = await task.promise;
    if (documentPdf.numPages > maximumPages) {
      throw new ReviewError('This PDF exceeds 40 pages. Choose a shorter document.');
    }

    const pages = [];
    let characters = 0;
    for (let number = 1; number <= documentPdf.numPages; number += 1) {
      if (current !== generation) return;
      status.textContent = `Reading page ${number} of ${documentPdf.numPages}…`;
      const page = await documentPdf.getPage(number);
      const content = await page.getTextContent();
      const lines = pageLines(content.items);
      characters += lines.reduce((sum, line) => sum + line.length, 0);
      if (characters > maximumCharacters) {
        throw new ReviewError('This PDF has too much text for one review. Split it and try again.');
      }
      pages.push({number, lines});
      page.cleanup();
    }
    if (current !== generation) return;
    show(explain(pages), documentPdf.numPages, {summary:treasurySummary(pages)});
    status.textContent = useSample ? (selectedSample === 'statement' ? 'Synthetic sample reviewed.' : 'Public Treasury sample reviewed.') : 'PDF reviewed in this browser.';
  } catch (failure) {
    if (current !== generation) return;
    error.textContent = failure instanceof ReviewError
      ? failure.message
      : (useSample || file.name.toLowerCase().endsWith('.pdf') ? 'This PDF could not be read. Try an intact PDF with selectable text and no password.' : 'This file could not be read. Try an intact XLSX or DOCX without a password.');
    error.hidden = false;
    status.textContent = 'Review could not finish.';
  } finally {
    clearTimeout(timeout);
    if (current === generation) {
      activeTask = undefined;
      sampleRequest = undefined;
      busy = false;
      controls();
      if (task) void task.destroy().catch(() => {});
    }
  }
}

fileInput.addEventListener('change', () => reset(fileInput.files.length ? 'File ready to explain.' : 'Choose a file or try a sample.'));
analyze.addEventListener('click', () => { void review(false); });
sample.addEventListener('click', () => { void review(true); });
clear.addEventListener('click', () => {
  fileInput.value = '';
  reset('Choose a file or try a sample.');
  fileInput.focus();
});

const statement = document.querySelector('#statement');
if ('IntersectionObserver' in window && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
  const words = statement.innerText.trim().split(/\s+/u).map(word => make('span', '', word));
  const reveal = new IntersectionObserver(([entry]) => {
    if (!entry.isIntersecting) return;
    reveal.disconnect();
    words.forEach((word, index) => setTimeout(() => word.classList.add('shown'), 45 * index));
  });
  const phrases = ['See where each finding comes from.', 'Decide what needs a closer look.'];
  const firstCount = phrases[0].split(' ').length;
  const spaced = words.flatMap((word, index) => [index === firstCount ? document.createElement('br') : ' ', word]);
  statement.replaceChildren(...spaced);
  statement.dataset.reveal = '';
  reveal.observe(statement);
}
