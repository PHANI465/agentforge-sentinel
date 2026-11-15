const form = document.querySelector('#iaf-form');
const question = document.querySelector('#question');
const transcript = document.querySelector('#transcript');
const status = document.querySelector('#iaf-status');
const submit = form.querySelector('button');
const suggestions = [...document.querySelectorAll('.iaf-prompts button')];

function line(speaker, text, className) {
  const message = document.createElement('article');
  message.className = 'iaf-message ' + className;
  const heading = document.createElement('h2');
  heading.className = 'title-4';
  heading.textContent = speaker;
  const paragraph = document.createElement('p');
  paragraph.className = 'body-3';
  paragraph.textContent = text;
  message.append(heading,paragraph);
  transcript.append(message);
  transcript.scrollTop = transcript.scrollHeight;
  while (transcript.children.length > 16) transcript.firstElementChild.remove();
  return message;
}

function sourceLink(relative, source) {
  const target = new URL(relative, location.origin);
  if (target.origin !== location.origin && target.href !== 'https://phaneendragavara.dev/') return;
  const link = document.createElement('a');
  link.className = 'body-6';
  link.href = target.href;
  link.textContent = source;
  return link;
}

async function ask(text) {
  submit.disabled = true;
  suggestions.forEach(button => {button.disabled = true;});
  status.textContent = 'Checking the project library…';
  line('You',text,'user');
  try {
    const response = await fetch('/iaf/ask', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({question:text}),
      signal:AbortSignal.timeout(12000),
    });
    if (!response.ok) throw new Error('request');
    const result = await response.json();
    if (result.kind === 'out_of_scope') {
      line('IAF','I can explain Sentinel and its public project author. Try asking about the workflow, dataset, or document review.','assistant');
    } else if (result.kind === 'answer' && ['answer','url','source'].every(key => typeof result[key] === 'string')) {
      const message = line('IAF',result.answer,'assistant');
      const link = sourceLink(result.url, result.source);
      if (link) message.append(link);
    } else throw new Error('response');
    status.textContent = '';
  } catch {
    status.textContent = 'IAF could not load an answer. Try again.';
  } finally {
    submit.disabled = false;
    suggestions.forEach(button => {button.disabled = false;});
    question.focus();
  }
}
form.addEventListener('submit', event => {
  event.preventDefault();
  const text = question.value.trim();
  if (!submit.disabled && text && text.length <= 400) {
    question.value = '';
    void ask(text);
  }
});
for (const suggestion of suggestions) {
  suggestion.addEventListener('click', () => {
    question.value = suggestion.textContent;
    form.requestSubmit();
  });
}
