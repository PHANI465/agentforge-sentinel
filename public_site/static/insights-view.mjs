import {catalog, checkStates} from './check-catalog.mjs';
import {comparison, node} from './review-charts.mjs';

function locationName(location, index) {
  const prefix = 'Document ' + (index + 1) + ' · ';
  if (location.page) return prefix + 'page ' + location.page + ', line ' + location.line;
  if (location.sheet) return prefix + location.sheet + ', row ' + location.row + ', column ' + location.column;
  return prefix + 'Word block ' + location.block;
}

export function renderChecks(checks, documents, title) {
  const section = node('section', 'insights');
  const heading = node('h3', 'heading-5', title);
  const items = node('div', 'insight-items');
  const evidence = node('aside', 'source-panel');
  const evidenceHeading = node('h4', 'heading-6', 'Source evidence');
  const source = node('div', 'source-excerpt', 'Choose a source below a finding.');
  source.tabIndex = -1;
  evidence.append(evidenceHeading, source);
  const layout = node('div', 'insight-layout');
  layout.append(items, evidence);
  const flags = checks.filter(result => result.status === 'flagged').length;
  const completed = checks.filter(result => result.status === 'flagged' || result.status === 'passed').length;
  section.append(heading, node('p', 'body-3', flags + ' flags · ' + completed + ' of ' +
    checks.length + ' listed checks completed'), layout);
  const rank = {flagged: 0, inconclusive: 1, passed: 2, 'not-applicable': 3, 'not-run': 4};
  for (const result of [...checks].sort((a, b) => rank[a.status] - rank[b.status])) {
    const item = node('article', 'insight-check');
    item.dataset.detector = result.id;
    item.dataset.outcome = result.status;
    const label = node('p', 'outcome body-6', checkStates[result.status]);
    item.append(label, node('h4', 'heading-6', catalog[result.id][0]), node('p', 'body-3', result.detail));
    if (result.values.length) {
      const table = node('table', 'insight-table');
      table.append(node('caption', 'title-4', 'Values used in this check'));
      for (const [name, value] of result.values) {
        const row = table.insertRow();
        const key = node('th', '', name);
        key.scope = 'row';
        row.append(key, node('td', '', value));
      }
      item.append(table);
      const closing = result.id === 'D02' ? result.values.filter(([name]) => name.endsWith('closing balance')) : [];
      if (closing.length === 2 && closing.every(([, value]) => Number.parseFloat(value) >= 0)) {
        item.append(comparison({title: 'Closing balance comparison', note: 'Figures use the printed summary values.',
          bars: closing.map(([label, text]) => ({label, text, value: Number.parseFloat(text)}))}));
      }
    }
    const links = node('ul', 'source-buttons');
    for (const entry of result.evidence) {
      const index = documents.findIndex(document => document.descriptor.id === entry.documentId);
      if (index < 0 || !entry.location) continue;
      const label = locationName(entry.location, index);
      const button = node('button', 'secondary button-sm', label);
      button.type = 'button';
      button.addEventListener('click', () => {
        if (matchMedia('(max-width: 760px)').matches) item.append(evidence);
        else layout.append(evidence);
        const back = node('button', 'secondary button-sm', 'Return to finding');
        back.type = 'button';
        back.addEventListener('click', () => button.focus());
        source.replaceChildren(node('p', 'title-4', label), node('p', 'excerpt body-6', entry.text.slice(0, 1200)), back);
        source.focus();
      });
      const listItem = node('li');
      listItem.append(button);
      links.append(listItem);
    }
    if (links.childElementCount) item.append(links);
    items.append(item);
  }
  return section;
}

export function renderPacket(records) {
  const figure = node('figure', 'packet-flow');
  figure.append(node('figcaption', 'heading-6', 'Records in this comparison'));
  const flow = node('ol', 'example-values');
  const names = {invoice: 'Invoice', order: 'Purchase order', delivery: 'Delivery receipt',
    payment: 'Payment', credit: 'Credit note', reversal: 'Reversal', baseline: 'Vendor baseline'};
  for (const [index, {packet}] of records.entries()) {
    const entry = node('li');
    entry.append(node('strong', '', names[packet.type] ?? 'Unmatched document'));
    entry.append(node('p', 'body-6', 'Document ' + (index + 1) + (packet.id ? ' · ' + packet.id : '')));
    if (packet.order) entry.append(node('p', 'body-6', 'Purchase order ' + packet.order));
    if (packet.invoice) entry.append(node('p', 'body-6', 'Invoice ' + packet.invoice));
    flow.append(entry);
  }
  figure.append(flow);
  return figure;
}
