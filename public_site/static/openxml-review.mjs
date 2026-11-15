import {unzipSync} from './vendor/fflate.mjs';

const maximumExpanded = 12_000_000;
const maximumEntries = 400;
const maxRows = 10000;
const maxCells = 120000;
const decoder = new TextDecoder('utf-8', {fatal: true});
const sheetNamespace = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
const wordNamespace = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
const relationships = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
const currencyDecimals = {USD:2, CAD:2, EUR:2, GBP:2, AUD:2, NZD:2, CHF:2, INR:2, JPY:0, KWD:3};

function packageEntries(bytes, format) {
  let size = 0;
  let entries = 0;
  const files = unzipSync(bytes, {filter(file) {
    entries += 1;
    if (entries > maximumEntries) throw new Error('This document exceeds the ZIP entry limit.');
    const relevant = format === 'docx' ? file.name === 'word/document.xml'
      : /^xl\/(?:workbook\.xml|_rels\/workbook\.xml\.rels|sharedStrings\.xml|worksheets\/[^/]+\.xml)$/.test(file.name);
    if (!relevant) return false;
    size += file.originalSize;
    if (size > maximumExpanded) throw new Error('This document exceeds the expanded text limit.');
    return true;
  }});
  return files;
}

function xml(files, name) {
  if (!files[name]) throw new Error('The file is missing a required document part.');
  const body = decoder.decode(files[name]);
  if (/<!DOCTYPE|<!ENTITY/i.test(body)) throw new Error('Unsupported XML declarations.');
  const doc = new DOMParser().parseFromString(body, 'application/xml');
  if (doc.getElementsByTagName('parsererror').length) throw new Error('A document part is malformed.');
  return doc;
}

const elements = (root, ns, tag) => Array.from(root.getElementsByTagNameNS(ns, tag));
const first = (root, ns, tag) => root.getElementsByTagNameNS(ns, tag)[0];
const valueText = (root, ns) => elements(root, ns, 't').map(part => part.textContent ?? '').join('');

function word(files) {
  const doc = xml(files, 'word/document.xml');
  const body = first(doc, wordNamespace, 'body');
  if (!body) throw new Error('The Word document has no body.');
  const lines = [];
  const paragraphs = elements(body, wordNamespace, 'p');
  const tables = elements(body, wordNamespace, 'tbl').length;
  if (paragraphs.length > 10000) throw new Error('The Word document exceeds the paragraph limit.');
  for (const child of body.children) {
    if (child.localName === 'p') lines.push(valueText(child, wordNamespace));
    if (child.localName === 'tbl') {
      for (const row of [...child.children].filter(node => node.localName === 'tr')) {
        lines.push([...row.children].filter(node => node.localName === 'tc')
          .map(cell => valueText(cell, wordNamespace)).join(' '));
      }
    }
  }
  return {kind:'Word document', lines:lines.map(line => line.trim()).filter(Boolean), paragraphs:paragraphs.length, tables};
}

function workbook(files) {
  const wb = xml(files, 'xl/workbook.xml');
  const rel = xml(files, 'xl/_rels/workbook.xml.rels');
  const targets = new Map([...rel.documentElement.children].filter(node => !node.hasAttribute('TargetMode'))
    .map(node => [node.getAttribute('Id'), node.getAttribute('Target')]));
  const names = elements(wb, sheetNamespace, 'sheet');
  if (names.length > 20) throw new Error('The workbook exceeds 20 sheets.');
  const shared = files['xl/sharedStrings.xml'] ? elements(xml(files, 'xl/sharedStrings.xml'), sheetNamespace, 'si')
    .map(entry => valueText(entry, sheetNamespace)) : [];
  let rowCount = 0;
  let cellCount = 0;
  let formulaCount = 0;
  const sheets = names.map(sheet => {
    const target = targets.get(sheet.getAttributeNS(relationships, 'id'));
    const path = target?.startsWith('/') ? target.slice(1) : 'xl/' + target;
    if (!/^xl\/worksheets\/[a-z0-9._-]+\.xml$/i.test(path)) throw new Error('Unsupported workbook sheet path.');
    const rows = elements(xml(files, path), sheetNamespace, 'row').map(row => {
      rowCount += 1;
      if (rowCount > maxRows) throw new Error('The workbook exceeds 10,000 rows.');
      const cells = new Map();
      for (const cell of elements(row, sheetNamespace, 'c')) {
        cellCount += 1;
        if (cellCount > maxCells) throw new Error('The workbook exceeds the cell limit.');
        const column = cell.getAttribute('r')?.match(/^[A-Z]+/)?.[0];
        if (!column) continue;
        if (first(cell, sheetNamespace, 'f')) {
          formulaCount += 1;
          continue;
        }
        const rawValue = first(cell, sheetNamespace, 'v')?.textContent ?? '';
        const type = cell.getAttribute('t');
        const value = type === 's' ? shared[Number(rawValue)] : type === 'inlineStr' ? valueText(cell, sheetNamespace)
          : !type || type === 'n' || type === 'str' ? rawValue : undefined;
        if (value?.trim()) cells.set(column, value.trim());
      }
      return {number:row.getAttribute('r'), cells};
    });
    return {name:sheet.getAttribute('name') ?? 'Sheet', rows};
  });
  return {kind:'Excel workbook', sheets, rowCount, formulaCount, cellCount};
}

export function readOpenXml(bytes, format) {
  const files = packageEntries(bytes, format);
  return format === 'docx' ? word(files) : workbook(files);
}

function minorUnits(text, digits) {
  const match = text?.match(/^([+-]?)((?:\d{1,3}(?:,\d{3})+)|\d{1,12})(?:\.(\d{1,3}))?$/);
  if (!match || (match[3]?.length ?? 0) > digits) return undefined;
  return BigInt((match[1] === '-' ? '-' : '') + match[2].replaceAll(',', '') +
    (match[3] ?? '').padEnd(digits, '0'));
}

export function summarizeSheet(sheet) {
  const header = sheet.rows.find(row => row.cells.size);
  const fields = new Map([...(header?.cells ?? [])].map(([column, value]) => [value.toLowerCase(), column]));
  const currency = fields.get('currency');
  const amount = fields.get('amount');
  const debit = fields.get('debit');
  const credit = fields.get('credit');
  if (!currency || (!amount && !(debit && credit))) return undefined;
  const split = Boolean(debit && credit && !amount);
  const totals = new Map();
  let counted = 0;
  let skipped = 0;
  for (const {cells} of sheet.rows.slice(sheet.rows.indexOf(header) + 1)) {
    if (!cells.size) continue;
    const unit = cells.get(currency)?.toUpperCase();
    const digits = currencyDecimals[unit];
    if (digits === undefined) { skipped += 1; continue; }
    const net = amount ? minorUnits(cells.get(amount), digits) : undefined;
    const incoming = split ? minorUnits(cells.get(credit) ?? '0', digits) : net > 0n ? net : 0n;
    const outgoing = split ? minorUnits(cells.get(debit) ?? '0', digits) : net < 0n ? -net : 0n;
    if ((!split && net === undefined) || (split && !cells.has(credit) && !cells.has(debit)) ||
        incoming === undefined || outgoing === undefined || incoming < 0n || outgoing < 0n) {
      skipped += 1;
      continue;
    }
    const total = totals.get(unit) ?? {digits, incoming:0n, outgoing:0n};
    total.incoming += incoming;
    total.outgoing += outgoing;
    totals.set(unit,total);
    counted += 1;
  }
  return {split, counted, skipped, totals};
}
