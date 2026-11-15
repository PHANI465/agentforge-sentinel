# IAF · I am Antifraud

[Open IAF](https://agentforge-sentinel.vercel.app/iaf.html). It covers AgentForge
Sentinel and the public work of its creator, Phaneendra Gavara. The curated
library lives in [iaf-knowledge.json](iaf-knowledge.json). Each entry has a
public source. Edit entries and redeploy to update what the assistant can say.

IAF retrieves up to three passages that match a question. By default it answers
from the highest-ranked passage. If an OpenAI key is configured, IAF optionally
asks the model to select one retrieved passage. The app validates the selected
ID and shows the canonical passage and source link. It sends the selected public
passages and matched topic phrases to OpenAI. A model failure, quota refusal, or
missing key leaves the library answer available.

## Add your OpenAI key on Vercel

1. Create an API key in your [OpenAI API project](https://platform.openai.com/api-keys).
2. In [Sentinel’s Vercel environment settings](https://vercel.com/pgavara1-3079s-projects/agentforge-sentinel/settings/environment-variables),
   add **IAF_OPENAI_API_KEY** with your API key as the value. Choose **Production**
   and mark it **Sensitive**.
3. Redeploy the current production deployment in Vercel. Open IAF and ask a project question.

Configure the key in Vercel. The browser, GitHub and chat do not need a copy.
A new deployment reads the new value. IAF uses OpenAI GPT-6 Luna (`gpt-6-luna`)
with reasoning effort set to `none` for passage selection. The app limits
model calls to 30 per UTC day and 300 per UTC month across instances.
It limits each question to 400 characters and sends a bounded output request.
These limits bound calls. OpenAI API usage is billed by the API project.

The checked-in `iaf-quota.sql` is already installed on the current demo
database. A fresh database requires applying it once after provisioning the
hosted runtime role with [bootstrap.py](bootstrap.py). The hosted runtime role
can invoke the reservation function. It has zero access to the usage table.
