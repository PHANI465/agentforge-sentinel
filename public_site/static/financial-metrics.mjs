const million = /^\$?([+-]?\d{1,3}(?:,\d{3})*|[+-]?\d{4,9})$/;
const amountLabels = ['Total Receipts', 'Total Outlays', 'Total Surplus (+) or Deficit (-)'];
const formatter = new Intl.NumberFormat('en-US', {maximumFractionDigits: 1});

function numberFrom(text) {
  const match = text.match(million);
  return match ? Number(match[1].replaceAll(',', '')) : undefined;
}

function reportedRow(lines, label) {
  const index = lines.findIndex(line => line === label || line.startsWith(label + ' '));
  if (index < 0) return undefined;
  const line = lines[index];
  for (const fragment of [line.slice(label.length), lines[index + 1] ?? '']) {
    const value = numberFrom(fragment.trim().split(/\s+/)[0]);
    if (value !== undefined) return value;
  }
}

export function treasurySummary(pages) {
  for (const {number: page, lines} of pages) {
    const start = lines.findIndex(line => /^Table 2\.\s+Summary of Budget and Off-Budget Results and Financing of the U\.S\. Government,\s+([A-Za-z]+ \d{4})\s+and Other Periods/i.test(line));
    if (start < 0) continue;
    const month = lines[start].match(/,\s+([A-Za-z]+ \d{4})\s+and Other Periods/i)[1];
    const end = lines.findIndex((line, index) => index > start && /^Table \d+\./.test(line));
    const table = lines.slice(start, end < 0 ? undefined : end);
    if (!table.some(line => /\[\$\s*millions\]/i.test(line))) continue;
    const [receipts, outlays, balance] = amountLabels.map(label => reportedRow(table, label));
    if (![receipts, outlays, balance].every(Number.isFinite) || receipts < 0 || outlays < 0 ||
        Math.abs(receipts - outlays - balance) > 1) continue;
    return {
      title: month + ' budget summary',
      note: 'Source page ' + page + ', Table 2, “This Month” column. USD millions as published. Treasury rounds each total separately.',
      bars: [
        {label:'Receipts', value:receipts, text:formatter.format(receipts)},
        {label:'Outlays', value:outlays, text:formatter.format(outlays)},
      ],
      metrics: [
        {label:balance < 0 ? 'Reported deficit' : 'Reported surplus', text:formatter.format(Math.abs(balance)) + ' million USD'},
        {label:'Outlays covered by receipts', text:outlays ? formatter.format(receipts / outlays * 100) + '%' : 'Unavailable'},
      ],
    };
  }
}
