# Inspect and benchmark routing decisions

## What the dashboard records

Open **Activity**, select **All recorded sessions** (or a known session), and
expand a **Router** row. New records include the chosen candidate/action,
model/effort/adapter, admitted alternatives, validated choice probabilities,
evaluator confidence/model, policy version, requested/used provider,
attempt/success/fallback flags and fixed reason codes. Provider-selection latency
and total router-command latency are separate measurements; total includes
command setup and admission. The row shows evaluator tokens and a base-rate
estimate; measured billed cost remains unknown. Overview totals cover only the
retained window. Models & providers shows the most recent provider status.

These fields require this version to be installed and a new instrumented
invocation. Old records are not backfilled. A successful selection means the
response was valid, not that the task succeeded or the selected model was best.
Confidence/probabilities describe the evaluator's choice, not a calibrated
probability of passing your task. The provider does not return a free-form
rationale; fixed status/fallback codes explain operational outcomes only.
Confidence/probabilities are retained for accepted Decisions results; refusal,
malformed responses and low-confidence fallback do not retain a score.

Request and session UUIDs are visible. The caller must supply a real session UUID
when it knows one; otherwise it is `unassigned`. Router, JSON collector and OTel
feeds remain separate. A shared session is not an automatic causal link to a
downstream task, and OTel response counts are not quality labels. No automatic
native dispatch, per-task grader, cross-feed outcome join or benchmark UI exists.

Only allowlisted metadata enters SQLite history (default 7 days / 500 events;
configurable). Descriptions, task summaries, outputs, raw requests/responses,
credentials, endpoints, exception text and prompt hashes are excluded. The CLI
result still includes the selected trusted candidate's description and a request
digest, so treat a redirected result file separately from sanitized history.
The compact summary and candidate descriptions are sent to OpenAI when an
authorized Decisions call runs. Local history privacy does not mean no API input
is transmitted. Do not put secrets in the trusted packet.

## A practical quality benchmark

1. Freeze representative tasks, allowed model/effort pairs, constraints, a
   deterministic acceptance check and a versioned rules fallback before testing.
   Keep tuning cases in `development`; reserve unseen cases in `holdout`. Cover
   routine transformations, bug fixes, ambiguous integration and constraint cases.
2. For each task/trial compare **rules**, **always GPT-6.1 Sol / low**, and
   **Decisions**. Use identical initial context, tools, permissions and enforced
   budgets. Randomize arm order, reset workspaces, and repeat at least 3 trials;
   expand the sample until uncertainty is acceptable. The fixed Sol baseline
   must be skipped when inadmissible, never force-enabled. This scaffold admits
   native choices offline from trusted suite evidence; it does not discover an
   account catalog or benchmark local servers. Verify availability when running.
3. Run each selected route only under separately authorized spending/execution.
   Apply the acceptance checker blind to the arm. Record actual model/effort,
   task pass/fail, failures/timeouts, end-to-end latency including evaluation,
   tools and retries, evaluator/downstream token usage, and measured billed cost
   only when available. A completed command is not automatically a task pass.
   Include failed trials; do not cherry-pick passing attempts. Fix a timeout
   before running and report its full elapsed time.
4. Compare paired case/trial blocks: task pass rate first, then latency, usage,
   and cost per passing task where all billed costs are known. Inspect routing
   failures and capability/budget violations separately. Tune on development
   only; rerun the untouched holdout. Selection agreement and confidence alone
   cannot establish quality. Repeated trials on a tiny set are not independent
   new tasks; this tool makes no significance or generalization claim.

## Offline scaffold (Python 3.11+, standard library)

```sh
# Pure admission and baseline plan; does not read saved settings or credentials.
python scripts/routing_benchmark.py plan assets/benchmarks/suite.synthetic.json

# Arithmetic demonstration ONLY. These outcomes were authored, not measured.
python scripts/routing_benchmark.py compare assets/benchmarks/suite.synthetic.json assets/benchmarks/outcomes.synthetic.json
```

The two holdout examples are public toy exercises, not a meaningful model
evaluation set. `csv_sort_exact` asks for a CSV transform: parse header `id,name`,
sort by integer id, keep quoted commas, output the same header and final newline.
Use input `id,name\n2,"B, C"\n1,A\n`, expected
`id,name\n1,A\n2,"B, C"\n`; reject malformed integer IDs. `inclusive_range_tests`
asks to fix `def inclusive(a,b): return list(range(a,b))`; assert
`inclusive(1,3)==[1,2,3]`, `inclusive(3,3)==[3]`,
`inclusive(3,1)==[]`, `inclusive(-2,0)==[-2,-1,0]`.
The conservation case only exercises admission and intentionally excludes Sol.
Check IDs refer to these specifications; the tool does not execute checkers.
Replace/extend the suite and implement your acceptance harness before real use.

For actual evidence set `synthetic: false` in **both** files, assign a new suite
ID, and supply frozen packets and acceptance checks. The command validates the
schema, admission and arithmetic, not the truth of externally supplied results.
It never reads the live ledger or writes benchmark results automatically.

Suite schema v1 is strict: `schema_version`, `suite_id`, `synthetic`, `cases`.
Each case has `id`, `split` (`development`/`holdout`), `check_id`, `packet`, and
optional trusted `overrides`. The packet uses the normal routing schema and
ceilings; actual execution still needs a harness to enforce those bounds. Rules
means the frozen packet's safe fallback; it is not a separately learned router.
The fixed Sol baseline is exactly `gpt-6.1-sol`, `low`, `native` and must have one
unambiguous admitted candidate. Local candidates are unavailable in this offline
scaffold. A no-admissible-route case is rejected, not relaxed.

Outcome schema v1 has `schema_version`, matching `suite_id`/`synthetic`, and
`observations`. Each row requires:

| Field | Meaning |
| --- | --- |
| `case_id`, `trial`, `arm` | Suite case, repeat 1–100, `rules` / `always_sol` / `decisions`; duplicates rejected. |
| `selected_candidate_id`, `actual_model`, `actual_effort` | Must match an admitted pair and the fixed baseline for its arm. |
| `execution_status`, `task_passed` | `completed` / `failed` / `timeout`; boolean acceptance result; failed/timeout cannot pass. |
| `end_to_end_ms`, `evaluator_ms` | Total integer milliseconds; evaluator integer or null, already included in total. |
| `evaluator_attempts`, `used_provider`, `evaluator_fallback` | Attempts, `decisions`/`rules` for Decisions arm, `rules` for rules, `fixed` for Sol; boolean fallback. Record actual fallback routes. |
| `evaluator_input_tokens`, `evaluator_output_tokens`, `downstream_input_tokens`, `downstream_output_tokens` | Nonnegative integers or null for unknown; count tools/retries consistently. |
| `measured_billed_cost_usd` | Nonnegative finite number or null; include evaluator and execution, never substitute an estimate or Codex credit conversion. |

Optional `confidence` is a finite 0–1 number or null, retained for external
calibration but never treated as a score by the comparator. Optional
`router_request_id`, `session_id`, `downstream_request_id` are explicit UUID
correlations supplied by the harness; `session_id` may be `unassigned`. They do
not create a link in the dashboard. No arbitrary prompt/output/rationale fields
are accepted. Keep evidence files private unless every entry is synthetic.

Reports separate development/holdout; headline metrics include only complete
three-arm blocks, list excluded/incomplete coverage and unknown token/cost
counts. Quantiles are median and nearest-rank p95; small samples are descriptive.
No missing trial is imputed. Selection overhead is not added twice. No API call,
task execution, billed-cost fetch, automatic export or benchmark scheduler exists.
