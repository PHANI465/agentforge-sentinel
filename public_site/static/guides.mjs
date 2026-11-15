import {catalog} from './check-catalog.mjs';
import {samples} from './insight-samples.mjs';
import {node} from './review-charts.mjs';

const examples = [
  ['purchase', 'Advanced', ['D06','D07','D09'], 'Look for a USD 20 unit-price difference, 50 fewer units delivered, and a changed destination identifier.'],
  ['statementgap', 'Intermediate', ['D02','D03'], 'The calculated closing balance is USD 1,300. The printed balance is USD 900.'],
  ['invoice', 'Intermediate', ['D01','D12'], 'The first line is overstated by USD 200. The printed payable total also differs by USD 10 after adjustments.'],
  ['ledger', 'Intermediate', ['D02','D11'], 'The printed closing value is formula-derived and excluded. The ledger shows eligible USD and EUR rows separately.'],
  ['duplicate', 'Intermediate', ['D04'], 'Two distinct files repeat the same invoice ID. The companion includes an identical copy that counts once.'],
  ['settlement', 'Advanced', ['D08'], 'After applying a credit, two installments and a reversal, the supplied records exceed the invoice by USD 20.'],
  ['policy', 'Advanced', ['D10'], 'Two USD 4,995 invoices in the same purchase group cross the example’s USD 5,000 threshold together.'],
  ['ambiguous', 'Intermediate', ['D02'], 'Conflicting printed balances make the check inconclusive. The companion shows an unambiguous decimal-comma layout.'],
];
const controlKeys = {statementgap: 'statementcontrol'};
const link = (label, href, style) => {
  const result = node('a', style, label);
  result.href = href;
  return result;
};
const capabilityCards = document.querySelector('#capability-cards');
if (capabilityCards) {
  for (const [id, [title, status, required, limit]] of Object.entries(catalog)) {
    const card = node('article');
    card.id = id;
    card.append(node('h2', 'heading-6', title), node('p', 'outcome body-6', status),
      node('p', 'body-3', required), node('p', 'body-3', limit));
    const related = examples.find(([, , checks]) => checks.includes(id));
    if (related) card.append(link('See an example', 'examples.html#' + related[0], 'sample-links body-6'));
    capabilityCards.append(card);
  }
}
const exampleCards = document.querySelector('#example-cards');
if (exampleCards) {
  for (const [key, difficulty, checks, expected] of examples) {
    const control = controlKeys[key] ?? key + 'control';
    const card = node('article');
    card.id = key;
    card.append(node('h2', 'heading-6', samples[key].title),
      node('p', 'body-6', 'Synthetic · ' + difficulty + ' · ' + samples[key].files.length + ' file(s)'));
    const links = node('div', 'sample-links body-6');
    links.append(link('Open review', './?sample=' + key + '#review', 'primary button-sm'),
      link('Open companion example', './?sample=' + control + '#review'));
    card.append(links);
    const downloads = node('details');
    downloads.append(node('summary', 'title-4', 'Download files and see checks'));
    const files = node('ul', 'body-6');
    const names = new Set([...samples[key].files, ...samples[control].files]);
    for (const file of names) {
      const li = node('li');
      const name = file.split('/').at(-1);
      const anchor = link(name, file);
      anchor.download = name;
      li.append(anchor);
      files.append(li);
    }
    downloads.append(files);
    for (const id of checks) {
      const p = node('p', 'body-6');
      p.append(link(catalog[id][0], 'capabilities.html#' + id));
      downloads.append(p);
    }
    const answer = node('details');
    answer.append(node('summary', 'title-4', 'Expected result'), node('p', 'body-3', expected));
    card.append(downloads, answer);
    exampleCards.append(card);
  }
  // The gallery metadata is public and never enters the document parser.
  fetch(new URL('./samples/insights/manifest.json', import.meta.url)).then(response => {
    if (!response.ok) return null;
    return response.json();
  }).then(manifest => {
    if (!manifest) return;
    for (const anchor of exampleCards.querySelectorAll('a[download]')) {
      const info = manifest.files[anchor.download];
      if (!info) continue;
      anchor.parentNode.append(' · ' + (info.bytes / 1000).toFixed(1) + ' kB' +
        (info.pages ? ' · ' + info.pages + (info.pages === 1 ? ' page' : ' pages') : ''));
    }
  }).catch(() => {});
}
