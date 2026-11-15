import {moneyToMinor} from './document-evidence.mjs';

export const normalize = text => text.trim().replace(/\s+/gu, ' ');

export function decimal(text, currency, comma = false) {
  const match = normalize(text).match(/^(?:([A-Z]{3}) )?(\(?-?(?:[$€£])?-?\d[\d,.]*\)?)(?: ([A-Z]{3}))?$/);
  if (!match || (match[1] && match[1] !== currency) || (match[3] && match[3] !== currency)) return undefined;
  let raw = match[2];
  const parenthesized = raw.startsWith('(') && raw.endsWith(')');
  if (parenthesized) raw = raw.slice(1, -1);
  if (raw.includes('(') || raw.includes(')') || (parenthesized && raw.includes('-')) ||
      (raw.includes('€') && currency !== 'EUR') || (raw.includes('£') && currency !== 'GBP') ||
      (raw.includes('$') && !['USD', 'CAD', 'AUD', 'NZD'].includes(currency))) return undefined;
  raw = raw.replace(/[$€£]/g, '');
  if (comma) {
    if (!/^-?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d{1,3})?$/.test(raw)) return undefined;
    raw = raw.replaceAll('.', '').replace(',', '.');
  } else {
    if (!/^-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,3})?$/.test(raw)) return undefined;
    raw = raw.replaceAll(',', '');
  }
  try { return moneyToMinor((parenthesized ? '-' : '') + raw, currency); } catch { return undefined; }
}

export function validDate(date) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date ?? '')) return false;
  const value = new Date(date + 'T00:00:00Z');
  return Number.isFinite(value.getTime()) && value.toISOString().slice(0, 10) === date;
}

export function check(id, status, detail, evidence = [], values = []) {
  return {id, status, detail, evidence, values};
}
