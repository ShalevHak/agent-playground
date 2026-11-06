# Agent Playground Iteration 1 — Implementation Plan

Spec: `docs/superpowers/specs/2026-11-06-agent-playground-design.md`

## Global Constraints
- Python **3.8 compatible**: no `match`, no `X | Y` types, no `list[str]` generics at runtime — use `typing.List`, `Optional`, `Dict`, `Tuple`. `from __future__ import annotations` is allowed.
- Dependencies: only stdlib + `pyyaml` + `pytest`.
- TDD: write the failing test first, see it fail, then implement. Every task commits its own work.
- Unit tests never call the real `claude` binary. Anything that would is injected as a `runner`.
- Runner signature: `Runner = Callable[[str, Path, str, float], ClaudeResult]` → `(prompt, cwd, agent, timeout_s)`.
- Terminal output ASCII only. Paths in reports use forward slashes, relative to the workspace.
- Run tests with `python -m pytest` from the repo root. `pytest.ini` sets `addopts = -m "not live"`.
- Commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## Task 1: Scaffold + lab loader

Files: `README.md` (short placeholder: title + "see labs/"), `requirements.txt` (`pyyaml>=5.4`, `pytest>=7`), `pytest.ini`, `.gitignore` (`__pycache__/`, `.pytest_cache/`, `runs/`, `.superpowers/`, `workspace/.claude/agents/*.md`), `workspace/.claude/agents/.gitkeep`, `scoring/__init__.py`, `scoring/lab.py`, `tests/__init__.py`, `tests/test_lab.py`, `tests/fixtures/labs/labx-sample/lab.yaml` (a minimal sample lab used only by tests; its `fixture/` dir with one file `a.py`).

`pytest.ini`:
```ini
[pytest]
testpaths = tests
addopts = -m "not live"
markers =
    live: calls the real claude CLI (costs tokens)
```

`scoring/lab.py` interface:
```python
REPO_ROOT = Path(__file__).resolve().parent.parent
LABS_DIR = REPO_ROOT / "labs"

@dataclass
class Expected:
    file: str
    line: int
    cause: str
    fix: str

@dataclass
class Variant:
    name: str
    overlay: Optional[Path]   # absolute, resolved against lab root; None if absent
    remove: List[str]         # fixture-relative posix paths to delete
    expected: Expected        # cause/fix inherited from base expected when omitted in yaml

@dataclass
class Lab:
    id: str
    root: Path
    title: str
    agent_name: str
    task_prompt: str
    fixture: Path             # root / "fixture"
    expected: Expected
    variants: List[Variant]
    line_tolerance: int
    time_budget_s: float
    timeout_s: float
    consistency_runs: int
    weights: Dict[str, float] # keys: structure, behavior, speed, robustness

class LabNotFound(Exception): ...

def load_lab(lab_id: str, labs_dir: Path = LABS_DIR) -> Lab
```
`load_lab("lab01")` finds the single directory in `labs_dir` named `lab01` or starting with `lab01-`; none → `LabNotFound` listing available lab dirs. Variant `expected` keys `file`/`line` required; `cause`/`fix` default to base. Missing required top-level key → `ValueError` naming the key.

Tests: loads sample lab with all fields; prefix match; unknown id raises `LabNotFound`; variant inherits cause/fix; missing key raises `ValueError`.

## Task 2: Workspace builder

Files: `scoring/workspace.py`, `tests/test_workspace.py`.

```python
def build_workspace(lab: Lab, variant: Optional[Variant], agent_file: Path,
                    parent: Optional[Path] = None) -> Path
def snapshot(ws: Path) -> Dict[str, str]          # posix relpath -> sha256 hex; skips anything under .claude/
def changed_files(before: Dict[str, str], after: Dict[str, str]) -> List[str]  # sorted; added, removed, or modified
```
`build_workspace`: `tempfile.mkdtemp(prefix="pg-", dir=parent)`; copy `lab.fixture` contents into it; if variant: copy overlay tree over it (overwrite), then delete each `remove` path; copy `agent_file` to `<ws>/.claude/agents/<lab.agent_name>.md`. Returns ws path. Caller deletes it.

Tests use the sample lab from Task 1 (add a `variants/v1/` overlay to it with one new file and one overwritten file, and a `remove` entry in its yaml).

## Task 3: Lab 01 content

Files: `labs/lab01-contract/{README.md, lab.yaml, fixture/..., variants/moved/..., variants/renamed/..., variants/decoy/..., solution/bug-hunter.md}`, `tests/agents/sloppy.md`, `tests/test_lab01_data.py`.

Fixture `shop/` package: `__init__.py`, `pricing.py`, `cart.py`, `formatting.py`, plus `README.md` describing the shop (no hint about the bug) and `tests/test_cart.py` (a plain test file in the fixture; it is content for the agent to read, not run by our suite — exclude via `testpaths = tests` already). Constants `BULK_THRESHOLD = 10`, `BULK_DISCOUNT = 0.10`. The bug: exactly one line `if qty > BULK_THRESHOLD:` in `shop/pricing.py`.

Variants:
- `moved`: overlay `shop/pricing.py` with extra helpers above, so the buggy line sits ≥ 8 lines lower.
- `renamed`: overlay adds `shop/rates.py` (the pricing code, bug inside) and an updated `shop/cart.py` importing from `rates`; `remove: [shop/pricing.py]`.
- `decoy`: overlay adds `shop/legacy_pricing.py`, an unused module with a suspicious comment (`# FIXME: discount math looks wrong`) over code that is unused; the real bug unchanged.

`lab.yaml` values:
```yaml
id: lab01
title: "Contract: a bug-hunter agent"
agent_name: bug-hunter
time_budget_s: 90
timeout_s: 240
consistency_runs: 3
line_tolerance: 2
weights: {structure: 0.2, behavior: 0.4, speed: 0.1, robustness: 0.3}
task_prompt: |
  Customers who buy exactly 10 units of an item are not getting the bulk
  discount. Buying 11 or more units works. Find the root cause in this
  repository and report it.
expected:
  file: shop/pricing.py
  line: <the real line number>
  cause: "Off-by-one: the bulk discount check uses `qty > BULK_THRESHOLD` instead of `qty >= BULK_THRESHOLD`, so exactly 10 units is excluded."
  fix: "Change the comparison to `qty >= BULK_THRESHOLD`."
variants: [moved, renamed, decoy with their real file/line]
```

`labs/lab01-contract/README.md` for learners: the concept (an agent contract = role, input, tools, steps, output format, stopping rule), the task, the **required report schema** — the agent's final answer must be only this JSON object: `{"file": "<repo-relative path>", "line": <int>, "cause": "<one sentence>", "fix": "<one sentence>"}` — where to write the agent (`workspace/.claude/agents/bug-hunter.md`), how to run (`python -m scoring.run lab01 --quick` then full), what each score means, 3 hints, and "don't peek at solution/".

`solution/bug-hunter.md`: frontmatter `name: bug-hunter`, a description, `tools: Read, Grep, Glob`; body with role, steps (read symptom → grep relevant terms → read candidates → confirm → report), JSON-only output with the four keys, stopping rule, and "never edit files".

`tests/agents/sloppy.md`: `name: bug-hunter`, `tools: Read, Grep, Glob`, body: "You help find bugs. Look around the code and tell me what you think is wrong." (passes the gate, nothing else).

Tests in `tests/test_lab01_data.py`: load lab01; for base and each variant build the workspace (Task 2) with the solution agent and assert the expected line (1-based) of the expected file contains `> BULK_THRESHOLD`; assert that string appears exactly once across all `.py` files in each workspace; `renamed` workspace has no `shop/pricing.py`; `decoy` workspace has `shop/legacy_pricing.py`.

## Task 4: JSON extraction

Files: `scoring/jsonx.py`, `tests/test_jsonx.py`.
```python
def extract_json_object(text: str) -> Tuple[Optional[dict], bool]   # (obj, strict)
```
strict=True when `text.strip()` parses as a dict. Else try the first ```` ```json ```` (or bare ```` ``` ````) fenced block; else the first balanced `{...}` (brace matching aware of JSON strings/escapes) that parses as a dict. Non-dict JSON → (None, False). Tests cover: strict, fenced, prose-wrapped, nested braces in strings, invalid, list.

## Task 5: Structure checker

Files: `scoring/structure.py`, `tests/test_structure.py`.
```python
READ_ONLY_TOOLS = {"Read", "Grep", "Glob"}
@dataclass
class Check:
    id: str
    passed: bool
    critical: bool
    hint: str        # shown when failed; "" when passed

@dataclass
class StructureResult:
    checks: List[Check]
    score: float      # 100 * passed / total
    gate_passed: bool # all critical checks passed

def check_structure(agent_file: Path, agent_name: str) -> StructureResult
```
Check ids in this order: `exists`*, `frontmatter`* (file starts with `---`, YAML block parses to a dict), `name_matches`* (`name == agent_name`), `description` (non-empty), `tools_declared` (`tools` key present, non-empty; string `"Read, Grep"` or list), `read_only_tools`* (every tool in READ_ONLY_TOOLS; fails if tools missing), `output_schema` (body contains each of the words file, line, cause, fix — case-insensitive word match), `json_only` (body contains "JSON", case-insensitive), `stopping_rule` (regex `\b(stop|stopping|done when|finish(ed)? when|as soon as)\b`, case-insensitive). `*` = critical. When an earlier check makes later ones impossible, they fail with hint `"fix the earlier error first"`. Hints are actionable one-liners. Tests: solution-like file passes all; sloppy file passes the gate but fails schema/json/stop; missing file; bad frontmatter; wrong name; `tools: Read, Edit` fails `read_only_tools`; list-form tools.

## Task 6: Claude CLI runner

Files: `scoring/claude_cli.py`, `tests/test_claude_cli.py`, `tests/fake_claude.py`.
```python
CLAUDE_FLAGS = ["--output-format", "stream-json", "--verbose", "--setting-sources", "project",
                "--strict-mcp-config", "--no-session-persistence"]

@dataclass
class ClaudeResult:
    result_text: str
    events: List[dict]
    duration_s: float
    timed_out: bool
    error: Optional[str]
    num_turns: Optional[int]
    cost_usd: Optional[float]

class ClaudeNotAvailable(Exception): ...

def find_claude() -> List[str]                      # [path] from shutil.which("claude"); else raise with install/login hint
def parse_stream(lines: Iterable[str]) -> Tuple[List[dict], Optional[dict]]  # all events, the last type=="result" event; skip blank/non-JSON lines
def run_claude(prompt: str, cwd: Path, agent: str, timeout_s: float,
               claude_cmd: Optional[List[str]] = None) -> ClaudeResult
```
Command: `claude_cmd + ["-p", "--agent", agent] + CLAUDE_FLAGS`; prompt on **stdin**; `encoding="utf-8", errors="replace"`; wall-clock `duration_s`. `error` set when: exit code ≠ 0 (include last 500 chars of stderr), no result event, or result `is_error` true. On `subprocess.TimeoutExpired`: `timed_out=True`, `error="timed out after Ns"`, parse whatever stdout was captured. `result_text` = result event's `result` (str) or "". `tests/fake_claude.py` is a script that reads stdin and, driven by env var `FAKE_CLAUDE_MODE` (`ok`, `error`, `sleep`, `noresult`), prints canned stream-json; tests call `run_claude(..., claude_cmd=[sys.executable, str(fake)])`.

## Task 7: Speed + behavior + robustness

Files: `scoring/speed.py`, `scoring/behavior.py`, `scoring/robustness.py`, `tests/test_speed.py`, `tests/test_behavior.py`, `tests/test_robustness.py`.

```python
# speed.py
def speed_score(duration_s: float, budget_s: float, timed_out: bool = False) -> float
# 100 if d <= b; 0 if timed_out or d >= 3b; else 100 * (3b - d) / (2b)

# behavior.py
REPORT_KEYS = ("file", "line", "cause", "fix")
@dataclass
class ParsedReport:
    data: Optional[dict]
    strict: bool
    error: Optional[str]

def parse_report(text: str) -> ParsedReport   # uses jsonx; requires all keys; file/cause/fix str, line int (not bool)
def normalize_path(p: str) -> str             # backslash->/, strip leading "./" and "/"
def file_matches(reported: str, expected: str) -> bool  # normalized equal, or reported ends with "/" + expected

@dataclass
class RunOutcome:
    run_id: str           # "base-1".."base-N", "variant-<name>"
    variant: str          # "base" or variant name
    report: ParsedReport
    file_match: bool
    line_match: bool
    edited_files: List[str]
    duration_s: float
    timed_out: bool
    error: Optional[str]
    result_text: str
    events: List[dict]
    passed: bool

def evaluate_run(run_id: str, variant: str, expected: Expected, line_tolerance: int,
                 result: ClaudeResult, edited_files: List[str]) -> RunOutcome
def code_behavior_score(outcome: RunOutcome) -> float   # 100 * mean([report valid, file_match, line_match])
def execute_runs(lab: Lab, agent_file: Path, runner: Runner, quick: bool = False,
                 on_progress: Optional[Callable[[str], None]] = None) -> List[RunOutcome]
```
`execute_runs`: base runs (1 if quick else `lab.consistency_runs`), then each variant (none if quick). Per run: build workspace, snapshot, call runner, snapshot, `changed_files`, evaluate, `shutil.rmtree(ws, ignore_errors=True)`. A runner exception becomes a failed outcome with `error=str(exc)` (never propagates). `on_progress("base-1")` before each run.

```python
# robustness.py
@dataclass
class RobustnessResult:
    score: Optional[float]
    consistent: Optional[bool]   # all base runs passed with identical (file, line)
    passed_runs: int
    total_runs: int
    skipped: bool

def score_robustness(outcomes: List[RunOutcome], quick: bool) -> RobustnessResult
# quick -> skipped=True, score=None, consistent=None; else score = 100 * passed / total
```
Tests use a fake runner returning `ClaudeResult`s; one fake runner writes a file into cwd to prove edit detection.

## Task 8: Judge

Files: `scoring/judge/judge-agent.md`, `scoring/judge.py`, `tests/test_judge.py`.
```python
JUDGE_AGENT_FILE = Path(__file__).parent / "judge" / "judge-agent.md"
JUDGE_TIMEOUT_S = 300
@dataclass
class JudgeResult:
    cause_score: Optional[float]
    fix_score: Optional[float]
    critique: str
    suggestions: List[str]
    error: Optional[str]

def tool_calls(events: List[dict], limit: int = 40) -> List[dict]  # [{"tool": name, "input": json str truncated to 200}], from assistant message content items of type "tool_use"
def build_judge_input(lab: Lab, agent_text: str, outcomes: List[RunOutcome]) -> dict
def parse_verdict(text: str) -> JudgeResult        # via jsonx; scores clamped 0..100; missing/invalid -> error set, scores None
def run_judge(lab: Lab, agent_text: str, outcomes: List[RunOutcome], runner: Runner) -> JudgeResult
```
`build_judge_input` keys: `lab` {id, title, task_prompt}, `expected` (base, as dict), `variant_expected` {name: dict}, `agent_definition`, `runs`: list of {run_id, variant, report (data or null), strict_json, result_text (truncated 2000), code_checks {file_match, line_match, edited_files, timed_out, error}, tool_calls}. `run_judge`: temp dir; copy judge agent to `.claude/agents/judge.md`; write `judge-input.json`; prompt `"Grade the submission described in judge-input.json in the current directory. Follow your instructions exactly."`; agent `"judge"`; parse; runner exception or error → `JudgeResult(None, None, "", [], error)`; clean up temp dir.

`judge-agent.md`: frontmatter `name: judge`, description, `tools: Read`. Body: role (strict, fair grader of a learner's bug-hunter agent), inputs (read judge-input.json once), rubric — `cause_score`: does each base run's cause correctly identify the off-by-one comparison and its effect (100 correct & precise across runs, 50 partial or inconsistent, 0 wrong/missing); `fix_score`: is the fix minimal and correct; critique: 3–6 sentences linking the agent definition's wording to observed behavior (what the contract got right, what caused failures); `suggestions`: up to 3 concrete prompt edits. Rule: code checks are ground truth for file/line — do not re-grade them. Output: only `{"cause_score": int, "fix_score": int, "critique": str, "suggestions": [str]}`. Stop after emitting the JSON.

Tests: tool_calls extraction; input shape; parse_verdict valid/clamp/invalid; run_judge with fake runner that asserts the agent file and input exist in cwd.

## Task 9: Report + CLI

Files: `scoring/report.py`, `scoring/run.py`, `scoring/__main__.py` not needed (`python -m scoring.run`), `tests/test_report.py`, `tests/test_run.py`.
```python
# report.py
@dataclass
class Scorecard:
    structure: float
    behavior: Optional[float]
    speed: Optional[float]
    robustness: Optional[float]
    total: Optional[float]

def compute_scorecard(lab: Lab, structure: StructureResult, outcomes: List[RunOutcome],
                      robustness: Optional[RobustnessResult], judge: Optional[JudgeResult]) -> Scorecard
def render(lab, scorecard, structure, outcomes, robustness, judge) -> str
def write_report(out_dir: Path, lab, scorecard, structure, outcomes, robustness, judge) -> Path
```
Behavior = `code_behavior_score(first base outcome)`; if judge has both scores: `0.5*code + 0.5*mean(cause, fix)`. Speed = mean `speed_score` over outcomes. Robustness = its score (None if skipped). No outcomes → behavior/speed/robustness None. Total = Σ w·s / Σ w over non-None dims, rounded to 1 decimal. `render` (ASCII): header with lab title; a table of the 4 scores + total (`-` for None); failed structure checks with hints; one line per run (`PASS/FAIL run_id  file:line  12.3s  reason`); judge critique + suggestions, or `judge unavailable: <error>`. `write_report`: `out_dir/report.json` (all of the above as JSON-safe dicts, events excluded) + `out_dir/transcripts/<run_id>.jsonl` (events). Returns report path.

```python
# run.py
def main(argv: Optional[List[str]] = None, runner: Optional[Runner] = None) -> int
```
Args: `lab_id`, `--quick`, `--agent-file` (default `REPO_ROOT/workspace/.claude/agents/<agent_name>.md`), `--runs-dir` (default `REPO_ROOT/runs`), `--no-judge`. Flow: load lab (LabNotFound → print, return 1); structure; if gate fails → print render + "fix the structure errors above before running", return 2; runner default: `find_claude()` (ClaudeNotAvailable → print message, return 3) wrapped as a Runner over `run_claude`; execute runs printing `running <run_id>...`; robustness; judge unless `--no-judge`; scorecard; print render; write report to `runs_dir/<YYYYmmdd-HHMMSS>`; print report path; return 0. `if __name__ == "__main__": sys.exit(main())`.

Tests: scorecard math (weights renormalized, judge fallback, None dims); render contains key lines; write_report files; `main` end-to-end with lab01 + a fake runner returning a correct strict report (exit 0, report.json exists, total ≥ 90 with fake perfect judge); gate failure exit 2 with missing agent file; unknown lab exit 1.

## Task 10: Live calibration + docs

Files: `tests/test_calibration_live.py`, `README.md` (full).
Live test (`@pytest.mark.live`): `main(["lab01", "--agent-file", <solution>, "--runs-dir", tmp])` → read report.json → total ≥ 90; same for `tests/agents/sloppy.md` → total ≤ 50.
README: what the playground is, prerequisites (Python 3.8+, `pip install -r requirements.txt`, Claude Code logged in), the lab list (Lab 01 now; 02 fan-out, 03 loop, 04 guardrails planned), how scoring works (4 scores, two checkers, cost ~7 calls, `--quick`), repo layout, how to add a lab (lab.yaml schema), running tests (`python -m pytest`; live: `python -m pytest -m live`).
