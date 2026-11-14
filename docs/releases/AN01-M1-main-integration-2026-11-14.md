# AN01-M1 prototype integration

On November 14, 2026, local main advanced to
`1427b2c8625eccdad39c123018aa0549d86287df`, the verified merge of
`5ef2b0d` and the accepted prototype `28dfcef`. The merge added the
prototype scripts, focused tests and documentation. The staged tree
`c4ebc174e72ed182a53cd11b654633d251ae8f4f` passed 158 focused tests
on each platform. The owner's separate Windows run passed the same 158.
[Prototype design and limits](../benchmarks/AN01-M1.md)

| Verification on 1427b2c | Windows | Native Ubuntu WSL |
| --- | --- | --- |
| Strict gate | Six checks passed | Six checks passed |
| Pytest | 1,099 passed and one allowed skip | 1,103 passed and one allowed skip |
| Same-run JUnit | 1,100 cases, validation passed | 1,104 cases, validation passed |
| HTTP export and ML reproduction | Passed | Passed |

Windows and Ubuntu ran sequentially. The single skip was the opt-in live
Claude smoke test. The first Windows run reported 1,098 passes and one
failure in the existing backward-clock deadline test. It measured 3.562 s
against a 3.5 s limit. The exact cause is unresolved. All ten clock tests
passed in isolation and the full rerun passed on the same commit with the
original assertion. The failed JUnit and strict report are preserved with
the Windows evidence in the integration checkout under
`.agent/an01-m1-integration/`. The final Windows JUnit is
`E:/PHANI/sentinel-tmp/an01-m1-1427b2c-windows.xml`. Ubuntu evidence is
under `/home/sentinel/codex-an01-m1-1427b2c-reports/`.

The synthetic replay fixture validated and its recorded-demo browser
checks passed 31/31 on Windows. The merge contains no changes to the
application, workbench or HTTP contracts. The earlier DOC01 tests cover
the current workbench code. The full-size AN01 measurement grid and
provisional limits remain open. Local commits use PHANI465 as sole author
and committer.
