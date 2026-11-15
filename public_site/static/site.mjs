import {explain, maximumBytes, maximumCharacters, maximumPages, pageLines} from './pdf-review.mjs';

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

function show(report, total) {
  const output = make('section', 'results');
  const heading = make('h3', 'heading-5', report.readable ? report.kind : 'No readable text found');
  heading.tabIndex = -1;
  output.append(heading);
  output.append(make('p', 'body-3', `Readable text on ${report.readable} of ${total} pages.`));
  if (report.missing.length) {
    output.append(make('p', 'body-3', `No readable text on ${report.missing.length === 1 ? 'page' : 'pages'} ${report.missing.join(', ')}. If these pages are scans, use a copy with selectable text.`));
  }
  if (report.readable) {
    if (report.findings.length) {
      const cards = make('ul', 'findings');
      for (const finding of report.findings) {
        const item = make('li');
        item.append(make('h4', 'title-3', finding.title));
        if (finding.amount) item.append(make('p', 'heading-5', finding.amount));
        item.append(
          make('p', 'body-6', finding.description),
          make('blockquote', 'body-6', finding.line.slice(0, 300)),
          make('span', 'caption-2', `Source page ${finding.page}`),
        );
        cards.append(item);
      }
      output.append(cards);
    } else {
      output.append(make('p', 'body-3', 'No supported labeled amounts or terms were found. Use the page excerpts below to review the extracted text.'));
    }
    output.append(make('p', 'caption-2', 'Findings use simple text rules. Amounts are quoted as printed. Tables and totals were not recalculated.'));
    const excerpts = make('details');
    excerpts.append(make('summary', 'title-3', 'Read page excerpts'));
    for (const excerpt of report.excerpts) {
      excerpts.append(make('p', 'title-4', `Page ${excerpt.page}`), make('p', 'excerpt body-6', excerpt.text));
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
  reset('Reading your PDF…');
  const current = generation;
  busy = true;
  clear.hidden = false;
  controls();
  let task;
  const timeout = setTimeout(() => {
    if (generation !== current) return;
    reset('Review stopped.');
    error.textContent = 'The PDF took too long to read. Try a shorter document.';
    error.hidden = false;
    clear.hidden = false;
  }, 25_000);
  try {
    let bytes;
    if (useSample) {
      sampleRequest = new AbortController();
      const response = await fetch(new URL('sample-statement.pdf', import.meta.url), {signal: sampleRequest.signal});
      if (!response.ok) throw new ReviewError('The sample could not load. Try again or choose a PDF.');
      bytes = await response.arrayBuffer();
    } else {
      if (file.size > maximumBytes) throw new ReviewError('This file exceeds 10 MiB. Choose a smaller PDF.');
      bytes = await file.arrayBuffer();
    }
    if (current !== generation) return;
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
    show(explain(pages), documentPdf.numPages);
    status.textContent = useSample ? 'Synthetic sample reviewed.' : 'PDF reviewed in this browser.';
  } catch (failure) {
    if (current !== generation) return;
    error.textContent = failure instanceof ReviewError
      ? failure.message
      : 'This PDF could not be read. Try an intact PDF with selectable text and no password.';
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

fileInput.addEventListener('change', () => reset(fileInput.files.length ? 'PDF ready to explain.' : 'Choose a PDF or try the sample.'));
analyze.addEventListener('click', () => { void review(false); });
sample.addEventListener('click', () => { void review(true); });
clear.addEventListener('click', () => {
  fileInput.value = '';
  reset('Choose a PDF or try the sample.');
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
