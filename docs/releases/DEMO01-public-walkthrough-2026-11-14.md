# Public Sentinel walkthrough

November 14, 2026 (America/Phoenix). The public walkthrough lets visitors
step through a recorded synthetic fraud case, from the rule score and
evidence to the investigation, scripted approval, simulated action and
audit trail. [Open the walkthrough](https://agentforge-sentinel-walkthrough.engagingfoxglove1.chatgpt.site)

The deployment uses the existing static viewer from project commit
`1188884392ade0f2d10eb69abf5a0795014ae596`. Its content consists of
`index.html`, `replay.js`, `replay.css`, `data/manifest.json` and
`data/recorded-case.json`. The main Sentinel repository and its runtime
stay outside the deployed source. The Site checkout is
`E:/PHANI/sentinel-walkthrough-site`. Its separate repository contains
the static files and the Sites manifest, at commit
`c2b1a7757521938c0dd36e71169de84d72c6a4e6`, with PHANI465 as sole author
and committer.

Sites confirmed public access and a successful version 1 deployment.
The project ID is `appgprj_6af9355ecf4c8191b6af99946753a3f2` and the
deployment ID is `appgdep_6af935ea52208191b581658fc8245aaa`. Reuse that
project for future updates. Keep the five-file allowlist when refreshing
the site from `demo/`.

The fixture validator confirmed all ten frames and recording SHA-256
`e52ea78926c99bfb5bcdf528f5af939ed673426ba5a69547015623129c5f4fd1`.
The same viewer passed the 31 recorded-demo browser checks in the
AN01 integration. Public HTTP requests fetched all five files without
authentication. The stylesheet, script and JSON files matched the
package byte for byte. The HTML matched after accounting for markup
inserted by the hosting edge. The in-app browser host was unavailable
for a separate hosted interaction check.
