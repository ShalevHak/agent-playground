# Agent Playground — Design (iteration 1)

## Intent

A self-paced playground that teaches a team **agentic development with Claude Code**
through hands-on labs. Each lab has a task, a learner-written artifact (agent, skill,
hook…), and an automatic scorer that is the teacher: it scores and explains.

Iteration 1 = the **scoring harness + Lab 01 (Contract)**. Later labs (fan-out, loop,
guardrails) add content only; the harness does not change.

### What the user said
- Audience: their team, self-paced (clone the repo, run labs alone).
- Tool: Claude Code (labs teach its real features).
- Score four dimensions: **Behavior, Structure, Speed, Robustness**.
- Two checkers: one **coded logic**, one **prompt-engineered agent (judge)**.
- Robustness = **consistency** (same task N times) + **variation** (tweaked tasks).
- Lab 01 task: a `bug-hunter` agent finds a planted bug and returns a strict JSON report.
- Runner: shell out to `claude -p`.

### Assumptions
- Python 3.8+ (user machine has 3.8.2), `pyyaml`, `pytest`. No other dependencies.
- Learners are logged into Claude Code; each full run costs ~7 `claude -p` calls.
- Windows and POSIX both supported (paths via `pathlib`, ASCII-only terminal output).

## Success criteria
1. `python -m scoring.run lab01` scores a learner agent on all four dimensions and
   prints a table plus a judge critique; writes `runs/<timestamp>/report.json`.
2. The reference `solution/` agent scores **≥ 90** total; a deliberately sloppy agent
   scores **≤ 50** (live calibration test).
3. Unit + integration tests run without network/tokens (fake runner).

## Repo layout

```
agent-playground/
  README.md
  requirements.txt            # pyyaml, pytest
  pytest.ini                  # marker `live`, excluded by default
  scoring/
    run.py                    # CLI: python -m scoring.run lab01 [--quick] [--agent-file P] [--runs-dir P] [--no-judge]
    lab.py                    # loads labs/<id>-*/lab.yaml into dataclasses
    workspace.py              # builds temp workspaces (fixture + variant overlay + agent), file snapshots
    claude_cli.py             # runs `claude -p` (stream-json), parses events, timeout, preflight
    jsonx.py                  # extract a JSON object from model text
    structure.py              # coded checks on the agent file
    behavior.py               # report parsing, per-run evaluation, executing all runs
    speed.py                  # time → score
    robustness.py             # consistency + variation score
    judge.py                  # builds judge input, runs judge agent, parses verdict
    judge/judge-agent.md      # the prompt-engineered judge
    report.py                 # scorecard, terminal table, report.json + transcripts
  labs/lab01-contract/
    README.md                 # concept, task, required schema, rules, hints
    lab.yaml                  # task prompt, expected answers, variants, budgets, weights
    fixture/                  # small Python "shop" repo with one planted bug
    variants/<name>/          # overlay files copied over the fixture
    solution/bug-hunter.md    # reference agent
  workspace/.claude/agents/   # learner writes bug-hunter.md here (gitignored except .gitkeep)
  tests/
```

## Scoring

All scores 0–100.

| Score | Checker | Rule |
|---|---|---|
| Structure | code | Fraction of checks passed on the agent file. Critical checks gate the run. |
| Behavior | code + judge | Base run 1: code part = mean(valid report, file match, line match); judge part = mean(cause_score, fix_score). Behavior = 0.5·code + 0.5·judge (code only if judge unavailable). |
| Speed | code | Per run: 100 if ≤ budget, linear to 0 at 3× budget, 0 if timed out. Mean over runs. |
| Robustness | code | 3 base runs + all variants; score = 100 · passed / total. Skipped in `--quick`. |

Total = weighted sum (lab weights: structure 0.2, behavior 0.4, speed 0.1, robustness 0.3),
renormalized over available dimensions.

A **run passes** when: report is valid, file matches, line within tolerance (±2), no files
edited, no timeout, no error.

### Structure checks (critical = gate)
`exists`*, `frontmatter`*, `name_matches`*, `description`, `tools_declared`,
`read_only_tools`* (only Read/Grep/Glob), `output_schema` (body names file, line, cause, fix),
`json_only` (body mentions JSON), `stopping_rule` (body states when to stop).
Gate failure → print hints and stop before spending tokens.

## Run flow
1. Structure check → gate.
2. For each run: copy fixture to temp dir, apply variant overlay/removals, copy the agent to
   `.claude/agents/<agent_name>.md`, snapshot hashes, run
   `claude -p --agent <name> --output-format stream-json --verbose --setting-sources project --strict-mcp-config --no-session-persistence`
   with the task prompt on stdin and a timeout, snapshot again, evaluate.
3. Judge: temp dir with `judge-agent.md` as agent `judge` and `judge-input.json`
   (expected answers, agent text, per-run reports, code checks, compact tool-call list).
   Returns JSON `{cause_score, fix_score, critique, suggestions}`.
4. Scorecard → terminal table + `runs/<timestamp>/report.json` + `transcripts/<run_id>.jsonl`.

## Errors
Timeouts, invalid JSON, file edits, CLI errors = failed runs with a reason, never a crash.
`claude` missing → exit 3 with a clear message. Gate failure → exit 2. Judge failure →
behavior falls back to code-only and the report says so.

## Lab 01 content
Fixture: `shop/` package (pricing, cart, formatting). Bug: bulk discount uses
`qty > BULK_THRESHOLD` instead of `>=`, so exactly 10 units gets no discount.
Variants: `moved` (bug on a different line), `renamed` (pricing module renamed to
`rates.py`), `decoy` (an unused legacy module with suspicious-looking code).

## Testing
- Unit tests per module; lab-data tests prove each expected line really holds the bug.
- Integration test: `run.main` end-to-end with a fake runner.
- Live calibration (`pytest -m live`): solution ≥ 90, sloppy ≤ 50.
