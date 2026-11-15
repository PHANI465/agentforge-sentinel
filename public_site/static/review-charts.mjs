import {summarizeSheet} from './openxml-review.mjs';

export function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

export function comparison({title, note, bars, metrics = []}) {
  const figure = node('figure', 'review-chart');
  figure.append(node('figcaption', 'heading-6', title));
  const max = Math.max(1, ...bars.map(bar => bar.value));
  const values = node('dl', 'chart-bars');
  for (const {label, value, text} of bars) {
    const row = node('div');
    const labelNode = node('dt', 'title-4', label);
    const description = node('dd');
    const meter = node('meter');
    meter.max = max;
    meter.value = value;
    meter.setAttribute('aria-hidden', 'true');
    description.append(meter, node('span', 'body-4', text));
    row.append(labelNode, description);
    values.append(row);
  }
  figure.append(values);
  if (metrics.length) figure.append(metricList(metrics));
  figure.append(node('p', 'caption-2', note));
  return figure;
}

export function metricList(items) {
  const section = node('dl', 'review-metrics');
  for (const {label, text} of items) {
    const item = node('div');
    item.append(node('dt','title-4',label),node('dd','body-4',text));
    section.append(item);
  }
  return section;
}

function amount(value, digits, currency) {
  const sign = value < 0n ? '−' : '';
  const absolute = value < 0n ? -value : value;
  const divisor = 10n ** BigInt(digits);
  const frac = digits ? '.' + String(absolute % divisor).padStart(digits,'0') : '';
  return sign + (absolute / divisor).toLocaleString('en-US') + frac + ' ' + currency;
}

export function renderWorkbook(report) {
  const output = node('section','results');
  const heading = node('h3','heading-5',report.kind);
  heading.tabIndex = -1;
  output.append(heading, metricList([
    {label:'Sheets read',text:String(report.sheets.length)},
    {label:'Worksheet rows read',text:String(report.rowCount)},
    {label:'Formula cells skipped',text:String(report.formulaCount)},
  ]));
  output.append(node('p','body-3','Financial totals are available for a header row containing Currency and either signed Amount or separate Debit and Credit columns. Formula cells are skipped.'));
  for (const sheet of report.sheets) {
    const section = node('details');
    section.append(node('summary','title-3',sheet.name));
    const summary = summarizeSheet(sheet);
    if (summary) {
      section.append(node('p','body-3',summary.counted + ' data rows counted. ' + summary.skipped + ' rows with unusable amounts or currency skipped.'));
      for (const [currency, total] of summary.totals) {
        const format = value => amount(value,total.digits,currency);
        section.append(comparison({
          title:currency + ' amounts',
          note:summary.split ? 'Uses the Credit and Debit columns from this sheet.' : 'Positive amounts count as credits and negative amounts count as debits.',
          bars:[
            {label:'Credits',value:Number(total.incoming),text:format(total.incoming)},
            {label:'Debits',value:Number(total.outgoing),text:format(total.outgoing)},
          ],
          metrics:[{label:'Credits minus debits',text:format(total.incoming - total.outgoing)}],
        }));
      }
      section.open = Boolean(summary.totals.size);
    } else section.append(node('p','body-3','No supported transaction headers in the first populated row. Review the preview to inspect the available columns.'));
    const sample = sheet.rows.filter(row => row.cells.size).slice(0,8)
      .map(row => 'Row ' + (row.number ?? '?') + ': ' + [...row.cells].map(([column,value]) => column + ' ' + value.slice(0,200)).join(' · '));
    if (sample.length) section.append(node('p','excerpt body-6',sample.join('\n')));
    output.append(section);
  }
  return output;
}
