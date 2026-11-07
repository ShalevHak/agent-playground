# agent-playground

A self-paced playground for learning agentic development with Claude Code.
Each lab gives you a small task, you write (or tune) a Claude Code agent for
it, and a scoring harness runs your agent against the real `claude` CLI and
tells you how well it did.

## Prerequisites

- Python 3.8+
- `pip install -r requirements.txt` (pyyaml, pytest)
- Claude Code installed and logged in (`claude` must work from your shell)

## Labs

| Lab | Topic | Status |
| --- | --- | --- |
| 01 | Contract: a read-only `bug-hunter` agent with strict JSON output | available |
| 02 | Fan-out: parallel sub-agents | planned |
| 03 | Loop: iterate until a check passes | planned |
| 04 | Guardrails: permissions and hooks | planned |

## Quick start

    pip install -r requirements.txt
    pip install -e .                    # installs the `agentplayground` command

    agentplayground                     # how the playground works
    agentplayground list                # see the labs
    agentplayground show lab01          # read the brief: concept, task, answer format
    agentplayground start lab01         # create your agent file from a starter
    agentplayground check lab01 --quick # score it fast while iterating
    agentplayground check lab01         # full scoring run

If `agentplayground` isn't found, pip's Scripts folder isn't on your PATH; use
`python -m agentplayground ...` instead.

Your agent lives in `workspace/.claude/agents/<agent>.md`. A reference solution
lives in each lab's `solution/` folder - try it yourself first.

## How scoring works

Four scores (0-100), combined by the weights in the lab's `lab.yaml`:

- **Structure** - static check of the agent file (frontmatter, name, tools,
  required sections). A failed structure gate stops the run before any
  tokens are spent.
- **Behavior** - did the agent report the right file and line (within a
  tolerance), as strict JSON, without editing anything? Blended 50/50 with
  the judge's cause/fix scores.
- **Speed** - time per run against the lab's `time_budget_s`.
- **Robustness** - consistency across repeated runs, and success on
  variants of the repo (code moved, file renamed, decoy file).

Two checkers produce these: a deterministic **code checker** (JSON, file,
line, tool use, timing) and an **LLM judge** (a separate claude call that
grades the cause and fix and writes a critique with suggested prompt
improvements).

Advanced: `agentplayground check` calls the scorer, which has extra options:

    python -m scoring.run lab01 --quick           # base run only (~2 claude calls)
    python -m scoring.run lab01 --no-judge        # skip the LLM judge
    python -m scoring.run lab01 --agent-file P    # score a file other than workspace/
    python -m scoring.run lab01 --runs-dir P      # where reports are written (default runs/)

A full run is about 7 claude calls (base x consistency runs, one per
variant, plus the judge). `--quick` is the fast inner loop; do a full run
before you call it done. Each run writes `report.json` and transcripts
under the runs directory.

Measured (Lab 01, real claude CLI): a full run of the reference solution
took about 90 seconds (7 calls, ~10-11s each); `--quick` took about 22
seconds. Token cost is not measured by the harness; each full run spends real tokens, so use `--quick` while iterating.

## Repo layout

    labs/<id>-<slug>/   lab.yaml, README.md, fixture/ (repo under test),
                        variants/ (overlays), solution/ (reference agent)
    scoring/            the harness (run.py is the entry point)
    workspace/          where you write your agent (.claude/agents/)
    tests/              unit tests (fake claude) and live calibration
    docs/               design spec and plan

## Adding a lab

In iteration 1 the harness supports read-only, single-agent labs that report a
file+line. The tool allowlist, report schema, edit policy and judge rubric become
per-lab config in iteration 2 (before Lab 02); until then a lab that needs more
than that needs harness changes.

Create `labs/labNN-slug/` with a `lab.yaml`, a `fixture/` repo, optional
`variants/`, and a `solution/`. All keys below are required except `remove`
and `overlay` inside a variant:

    id: labNN                    # matches the directory prefix
    title: "Short title"
    agent_name: bug-hunter       # agent file name the harness expects
    time_budget_s: 90            # full speed score at or under this
    timeout_s: 240               # per-run hard limit
    consistency_runs: 3          # repeated base runs for robustness
    line_tolerance: 2            # accepted distance from expected line
    weights: {structure: 0.2, behavior: 0.4, speed: 0.1, robustness: 0.3}
    task_prompt: |               # what the agent is asked
      ...
    expected:
      file: path/in/fixture.py
      line: 16
      cause: "what the judge compares against"
      fix: "the expected fix"
    variants:
      - name: moved
        overlay: variants/moved  # files copied over the fixture
        remove: [path/to/delete] # optional
        expected: {file: path.py, line: 31}

## Running the tests

    python -m pytest             # unit tests; never calls the real claude
    python -m pytest -m live -s  # live calibration; spends real tokens

The live tests check that the reference solution scores at least 90 and the
deliberately sloppy agent (`tests/agents/sloppy.md`) scores at most 50.
