# Implementation verification — 2026-10-15

Base commit: `a41de9d` on `main`. Work isolated in a fresh clone and branch
`feat/decisions-routing`; no unrelated checkout or HeurChain operations changed.

## Sources and compatibility

- [Official model guidance](https://learn.chatgpt.com/docs/models): current
  `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`; rollout and client
  availability remain account-dependent.
- [Official Decisions guide](https://developers.openai.com/api/docs/guides/decisions):
  `POST /v1/decisions`, Luna evaluator, choice/refusal/confidence/distribution
  contract, pricing and availability boundary.
- Installed CLI `0.162.1`, local catalog fetched 2026-10-15 (catalog client
  `0.162.0`): all four models visible. Luna supports low/medium/high/xhigh/max;
  the other three also expose ultra. No `none` effort in this Codex catalog.
  Every bundled native profile's updated model/effort was checked against it.
  This was catalog validation, not a metered completion or entitlement test.

## Checks performed

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -v` | 30 offline tests pass on bundled Python 3.12 / Windows. No external model requests. |
| CLI example, default provider | Returns `stay_sol_low` from offline rules. |
| CLI example, Decisions without `--allow-api` | Returns same route with `api_not_authorized`; no request. |
| PowerShell 7 installer, twice, isolated sibling fixture | New source files match installed copies; Sol general profile installed; one marked block; unrelated UTF-8 instructions preserved; no `config.toml` created. |
| Windows PowerShell 5.1 installer, same fixture | Pass. Actual personal skill/global instructions unchanged. |
| Git Bash `sh -n scripts/install.sh` | Pass. Full Unix installer not run on this Windows host. |
| `git diff --check` | Pass. |
| Skill Creator `quick_validate.py` | Could not run: bundled Python lacks optional PyYAML. Frontmatter inspected; no dependency installed. |

An offline GitHub Actions matrix was added for Python 3.11/3.12 on Windows and
Ubuntu. The initial 26-test commit `0603a3d` passed all four matrix jobs on push;
the numeric-overflow regression and single-candidate/count-limit review fixes add
four more offline tests. The 27-test commit `422aea3` also passed all matrix jobs.
Read PR checks for the latest exact-commit matrix status.

The first test invocation encountered sandbox restrictions in the process's
default temporary directory; the fixture was moved under the isolated task
directory, and the final suite passes. The first Git Bash syntax invocation was
blocked by the sandbox's MSYS initialization restrictions; the read-only syntax
check succeeded with the existing execution approval path.

## Remaining validation and limits

No metered API call, local inference probe, production deployment, global
installation, new credential or OAuth grant occurred. A live Decisions smoke
test needs explicit spending/data authorization, an existing suitable API key,
account access/quota, and outbound HTTPS. Real routing quality, confidence
calibration, latency and billing remain unmeasured. See
[the provider reference](decision-providers.md) for the exact smoke-test needs.

The helper provides recommendations and budget admission only. The parent and
actual dispatch adapter must recheck current capacity and enforce execution
token/spend/deadline limits. There is no JEV integration contract in this repo.
