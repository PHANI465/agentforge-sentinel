import {maximumBytes, maximumCharacters, maximumPages, pageLines} from './pdf-review.mjs';
import {evidenceLimits} from './document-evidence.mjs';
import {readOpenXmlParts} from './openxml-review.mjs';

export class ReviewError extends Error {}
const moduleUrl = path => new URL(path, import.meta.url);

export function reviewWorker(signal) {
  const worker = new Worker(moduleUrl('./document-worker.mjs'), {type: 'module'});
  const stop = () => worker.terminate();
  signal.addEventListener('abort', stop, {once: true});
  return {
    run(request, transfer = []) {
      return new Promise((resolve, reject) => {
        signal.throwIfAborted();
        function done(callback, value) {
          signal.removeEventListener('abort', abort);
          worker.onmessage = worker.onerror = worker.onmessageerror = null;
          callback(value);
        }
        function abort() { done(reject, signal.reason); }
        signal.addEventListener('abort', abort, {once: true});
        worker.onmessage = ({data}) => data.ok ? done(resolve, data.value) :
          done(reject, new ReviewError('This file could not be read. Check its format and size.'));
        worker.onerror = worker.onmessageerror = () =>
          done(reject, new ReviewError('The document reader stopped. Try again.'));
        try {
          worker.postMessage(request, transfer);
        } catch (error) {
          done(reject, error);
        }
      });
    },
    close() { signal.removeEventListener('abort', stop); stop(); },
  };
}

export function validateFiles(files) {
  if (!files.length || files.length > evidenceLimits.documents) throw new ReviewError('Choose 1 to 10 documents.');
  let total = 0;
  return files.map(file => {
    if (!file.size || file.size > maximumBytes) throw new ReviewError('This file is empty or exceeds 10 MB. Choose a supported file.');
    total += file.size;
    if (total > evidenceLimits.totalBytes) throw new ReviewError('The files exceed 20 MB together.');
    const format = file.name.split('.').at(-1).toLowerCase();
    if (!['pdf', 'xlsx', 'docx'].includes(format)) {
      throw new ReviewError('Choose PDF, XLSX or DOCX. Save an older Word DOC file as DOCX first.');
    }
    return {file, format};
  });
}

export async function readSample(path, format, signal, budget) {
  const response = await fetch(moduleUrl(path), {signal});
  if (!response.ok || !response.body) throw new ReviewError('The sample could not load. Try again.');
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    for (;;) {
      const {done, value} = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maximumBytes || size > budget) throw new ReviewError('The sample exceeds the review size limit.');
      chunks.push(value);
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
  if (!size) throw new ReviewError('The sample is empty.');
  return {file: new Blob(chunks), format};
}

async function readPdf(data, signal, progress) {
  if (!new TextDecoder().decode(data.subarray(0, 1024)).includes('%PDF-')) {
    throw new ReviewError('This file does not have a PDF header. Choose a PDF file.');
  }
  const pdf = await import('./vendor/pdfjs/pdf.min.mjs');
  signal.throwIfAborted();
  const worker = new Worker(moduleUrl('./vendor/pdfjs/pdf.worker.min.mjs'), {type: 'module'});
  let task;
  let stopPromise;
  const stop = () => {
    if (!stopPromise) stopPromise = task.destroy().catch(() => {}).finally(() => worker.terminate());
    return stopPromise;
  };
  let rejectAbort;
  const aborted = new Promise((_, reject) => { rejectAbort = reject; });
  const abort = () => {
    rejectAbort(signal.reason);
    void stop();
    worker.terminate();
  };
  try {
    task = pdf.getDocument({
      data, worker: new pdf.PDFWorker({port: worker}),
      isEvalSupported: false, disableFontFace: true, useSystemFonts: false,
      useWasm: false, stopAtErrors: true, cMapUrl: moduleUrl('./vendor/pdfjs/cmaps/').href,
    });
    signal.addEventListener('abort', abort, {once: true});
    const extract = async () => {
      task.onPassword = () => abortPassword();
      const document = await task.promise;
      if (document.numPages > maximumPages) {
        throw new ReviewError('This PDF exceeds 40 pages. Choose a shorter document.');
      }
      const pages = [];
      let characters = 0;
      for (let number = 1; number <= document.numPages; number += 1) {
        signal.throwIfAborted();
        progress(number, document.numPages);
        const page = await document.getPage(number);
        const reader = page.streamTextContent().getReader();
        const items = [];
        try {
          for (;;) {
            const {done, value} = await reader.read();
            if (done) break;
            characters += value.items.reduce((sum, item) => sum + (item.str?.length ?? 0) + 1, 0);
            if (characters > maximumCharacters) throw new ReviewError('This PDF has too much text for one review.');
            items.push(...value.items);
          }
        } finally {
          void reader.cancel().catch(() => {});
          reader.releaseLock();
        }
        pages.push({number, lines: pageLines(items)});
        page.cleanup();
      }
      return {pages};
    };
    const abortPassword = () => {
      rejectAbort(new ReviewError('This PDF could not be read. Choose a copy without a password.'));
      void stop();
    };
    return await Promise.race([aborted, extract()]);
  } finally {
    try {
      if (task && !signal.aborted) await Promise.race([stop(), aborted]).catch(() => {});
    } finally {
      signal.removeEventListener('abort', abort);
      worker.terminate();
    }
  }
}

export async function readDocument({file, format}, id, signal, worker, progress) {
  const data = new Uint8Array(await file.arrayBuffer());
  signal.throwIfAborted();
  if (!data.byteLength || data.byteLength > maximumBytes) throw new ReviewError('The file exceeds the review size limit.');
  const bytes = data.byteLength;
  const digest = await crypto.subtle.digest('SHA-256', data);
  const sha256 = [...new Uint8Array(digest)].map(value => value.toString(16).padStart(2, '0')).join('');
  signal.throwIfAborted();
  const descriptor = {id, format, bytes, sha256};
  if (format === 'pdf') return {descriptor, ...await readPdf(data, signal, progress)};
  const parts = await worker.run({type: 'office', format, data}, [data.buffer]);
  signal.throwIfAborted();
  const office = readOpenXmlParts(parts, format);
  if (format === 'xlsx') return {descriptor, workbook: office};
  if (office.lines.reduce((sum, line) => sum + line.length, 0) > maximumCharacters) {
    throw new ReviewError('This document has too much text for one review.');
  }
  return {descriptor, word: office, pages: [{number: 1, lines: office.lines}]};
}
