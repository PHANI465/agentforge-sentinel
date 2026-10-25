# AgentForge Sentinel

A fraud investigation workbench: synthetic financial transactions, rule or trained-model scoring, bounded investigations, analyst review, human-approved simulated actions and an audit history.

Start with [the project checkpoint](docs/PROJECT_CHECKPOINT.md) for the summary, step-by-step progress, saved Cursor state and next actions. [Current status](docs/STATUS.md), [the task queue](docs/TASK_QUEUE.md) and [the milestone roadmap](docs/PROJECT_PLAN.md) record acceptance and future work.

Accepted task branches include the local analyst/browser workflow, synthetic data, offline classical ML, backend reliability and C07 trained-model serving at 275509a. Cursor's model-analysis frontend at a5716e2 is accepted for the current-p1 contract/UI increment. Claude I01 and Cursor I02 now cover real model-browser integration. The components have not yet been accepted together as one browser/model stack or merged into main.

This checkout is task/coordination: current instructions and reviews on the older c6 application source. Main still holds the baseline. Use the named task dependencies for implementation; do not assume this checkout contains the latest complete product. [Setup](SETUP.md) describes its local thin path.

Broader multi-agent investigations, hosted staging, public visitor-key access and advanced risk/AI tracks remain milestone work. All current data and actions are synthetic or simulated. No real-bank efficacy or production-scale claim is made.
