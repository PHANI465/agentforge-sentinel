const get = id => document.getElementById(id);
const digest = 'e52ea78926c99bfb5bcdf528f5af939ed673426ba5a69547015623129c5f4fd1';
const dollars = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });

async function loadRecording() {
  const response = await fetch('data/recorded-case.json', {credentials: 'omit'});
  if (!response.ok) throw new Error('Recording unavailable');
  const bytes = await response.arrayBuffer();
  const hashed = await crypto.subtle.digest('SHA-256', bytes);
  const hash = Array.from(new Uint8Array(hashed), digit => digit.toString(16).padStart(2, '0')).join('');
  if (hash !== digest) throw new Error('Recording failed verification');
  return JSON.parse(new TextDecoder().decode(bytes));
}

function chapters(recording) {
  const r = recording.records;
  const txn = r.ingests.find(entry => entry.transaction.id === r.alert.transaction_id).transaction;
  const amount = dollars.format(txn.amount.minor_units / 10 ** txn.amount.currency_exponent);
  const prior = r.evidence.flatMap(entry => entry.facts).find(fact => fact.name === 'transaction_count_1h').value;
  const sameAction = r.replay.replayed && r.execution.action.id === r.replay.action.id;
  return [
    {
      label: 'Spot the risk',
      title: 'A large debit triggers an alert',
      story: 'After four earlier small debits, the account receives a ' + amount + ' debit. The scoring rule evaluates the amount and recent activity.',
      factLabel: 'Rule score and alert cutoff',
      fact: r.alert.score.toFixed(2) + ' vs ' + r.alert.threshold.toFixed(2),
      meaning: 'The score crosses the alert cutoff and opens a case. A rule score expresses the strength of the rule match.',
    },
    {
      label: 'Check evidence',
      title: 'Investigators check the activity behind the alert',
      story: 'The evidence analyst gathers the transaction and recent account activity. The investigator proposes a step. The reviewer checks the proposal against the evidence.',
      factLabel: 'Earlier debits in the previous hour',
      fact: String(prior),
      meaning: 'Sentinel checks claims against stored records. The reviewers’ work ends in a recommendation for a simulated hold.',
    },
    {
      label: 'Ask for approval',
      title: 'The proposal waits for a decision',
      story: 'The server prepares a proposal tied to this exact transaction and case. An analyst must approve it before the action can go ahead.',
      factLabel: 'Proposed action',
      fact: 'Simulated hold on ' + amount,
      meaning: 'The demo script records approval to show the approval step. A recommendation from the investigation cannot authorize an action.',
    },
    {
      label: 'Execute once',
      title: 'The approved action runs in the simulator',
      story: 'Execution checks that the approval belongs to this proposal. Sentinel records one successful simulated hold.',
      factLabel: 'Recorded simulated action',
      fact: r.execution.action.state === 'succeeded' ? '1 successful hold' : 'Action requires review',
      meaning: sameAction ? 'The same execution request is sent again. The server returns the original action record.' : 'The retry does not match the original action.',
    },
    {
      label: 'Review the audit',
      title: 'The audit explains how the case closed',
      story: 'The case records who approved the proposal, when it ran and which evidence was used. An analyst can review those records later.',
      factLabel: 'Final case status',
      fact: r.case_final.state === 'closed' ? 'Closed' : r.case_final.state,
      meaning: 'The technical replay shows the ten recorded events and the original API records behind this summary.',
    },
  ];
}

async function start() {
  const steps = chapters(await loadRecording());
  const buttons = [];
  let current = 0;
  const go = (index, focus = true) => {
    const item = steps[index];
    if (!item) return;
    current = index;
    buttons.forEach((button, number) => {
      if (number === index) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
    get('walk-count').textContent = 'Step ' + (index + 1) + ' of ' + steps.length;
    get('walk-title').textContent = item.title;
    get('walk-story').textContent = item.story;
    get('walk-fact-label').textContent = item.factLabel;
    get('walk-fact').textContent = item.fact;
    get('walk-meaning').textContent = item.meaning;
    get('walk-back').disabled = index === 0;
    get('walk-next').textContent = index === steps.length - 1 ? 'Start again' : 'Next';
    if (focus) get('walk-title').focus();
  };
  for (const [index, step] of steps.entries()) {
    const li = document.createElement('li');
    const button = document.createElement('button');
    const number = document.createElement('span');
    button.type = 'button';
    button.className = 'secondary button-sm';
    number.textContent = String(index + 1);
    button.append(number, document.createTextNode(step.label));
    button.addEventListener('click', () => go(index));
    li.append(button);
    get('walk-steps').append(li);
    buttons.push(button);
  }
  get('walk-back').addEventListener('click', () => go(current - 1));
  get('walk-next').addEventListener('click', () => go((current + 1) % steps.length));
  go(0, false);
  get('walk').hidden = false;
  get('walk-status').hidden = true;
}
void start().catch(() => {
  get('walk-status').textContent = 'The recording could not be verified. Refresh to try again.';
});
