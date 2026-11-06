import json
from pathlib import Path

import pytest

from scoring.behavior import (code_behavior_score, evaluate_run, execute_runs, file_matches,
                              normalize_path, parse_report)
from scoring.claude_cli import ClaudeResult
from scoring.lab import Expected, load_lab

LABS = Path(__file__).parent / "fixtures" / "labs"
GOOD = {"file": "a.py", "line": 1, "cause": "c", "fix": "f"}


def res(text="", duration=2.0, timed_out=False, error=None):
    return ClaudeResult(result_text=text, events=[{"type": "result"}], duration_s=duration,
                        timed_out=timed_out, error=error, num_turns=1, cost_usd=0.0)


@pytest.fixture
def lab():
    return load_lab("labx", LABS)


@pytest.fixture
def agent(tmp_path):
    f = tmp_path / "agent.md"
    f.write_text("x", encoding="utf-8")
    return f


# parse_report
def test_parse_strict():
    p = parse_report(json.dumps(GOOD))
    assert p.data == GOOD and p.strict and p.error is None


def test_parse_non_strict():
    p = parse_report("Here:\n```json\n%s\n```" % json.dumps(GOOD))
    assert p.data == GOOD and not p.strict and p.error is None


def test_parse_no_json():
    p = parse_report("nothing")
    assert p.data is None and not p.strict and p.error == "no JSON object found"


def test_parse_missing_keys():
    p = parse_report(json.dumps({"file": "a.py", "line": 1}))
    assert p.data is None and not p.strict and "cause" in p.error and "fix" in p.error


@pytest.mark.parametrize("key,val", [("file", 3), ("line", "1"), ("line", True), ("cause", None),
                                      ("fix", 1.5)])
def test_parse_wrong_types(key, val):
    d = dict(GOOD)
    d[key] = val
    p = parse_report(json.dumps(d))
    assert p.data is None and not p.strict and key in p.error


# paths
def test_normalize_path():
    assert normalize_path(r".\src\a.py") == "src/a.py"
    assert normalize_path("/src/a.py") == "src/a.py"


def test_file_matches():
    assert file_matches("a.py", "a.py")
    assert file_matches("./a.py", "a.py")
    assert file_matches("proj/src/a.py", "src/a.py")
    assert not file_matches("proj/xsrc/a.py", "src/a.py")
    assert not file_matches("b.py", "a.py")


# evaluate_run
EXP = Expected(file="a.py", line=10, cause="c", fix="f")


def test_evaluate_pass():
    o = evaluate_run("base-1", "base", EXP, 2, res(json.dumps(dict(GOOD, line=12))), [])
    assert o.file_match and o.line_match and o.passed and o.duration_s == 2.0
    assert o.events == [{"type": "result"}] and o.error is None
    assert code_behavior_score(o) == 100


def test_evaluate_line_off():
    o = evaluate_run("base-1", "base", EXP, 2, res(json.dumps(dict(GOOD, line=13))), [])
    assert o.file_match and not o.line_match and not o.passed
    assert code_behavior_score(o) == pytest.approx(200 / 3)


def test_evaluate_invalid_report():
    o = evaluate_run("base-1", "base", EXP, 2, res("no json"), [])
    assert not o.file_match and not o.line_match and not o.passed
    assert code_behavior_score(o) == 0


def test_evaluate_timeout_and_error_fail():
    txt = json.dumps(dict(GOOD, line=10))
    assert not evaluate_run("r", "base", EXP, 2, res(txt, timed_out=True), []).passed
    assert not evaluate_run("r", "base", EXP, 2, res(txt, error="boom"), []).passed


# execute_runs
def test_run_order_and_expected(lab, agent):
    calls, progress = [], []

    def runner(prompt, cwd, name, timeout):
        calls.append((prompt, name, timeout, (Path(cwd) / "b.py").exists()))
        return res(json.dumps({"file": "a.py", "line": 1, "cause": "c", "fix": "f"}))

    outs = execute_runs(lab, agent, runner, on_progress=progress.append)
    ids = ["base-1", "base-2", "base-3", "variant-inherit", "variant-v1"]
    assert [o.run_id for o in outs] == ids == progress
    assert [o.variant for o in outs] == ["base"] * 3 + ["inherit", "v1"]
    assert all(c[:3] == ("Find the bug.", "sample-agent", 120.0) for c in calls)
    assert [c[3] for c in calls] == [False, False, False, False, True]
    assert [o.passed for o in outs] == [True, True, True, True, False]  # v1 expects b.py


def test_quick_only_base_1(lab, agent):
    calls = []

    def runner(prompt, cwd, name, timeout):
        calls.append(1)
        return res(json.dumps(GOOD))

    outs = execute_runs(lab, agent, runner, quick=True)
    assert [o.run_id for o in outs] == ["base-1"] and len(calls) == 1


def test_edit_detection_and_cleanup(lab, agent):
    seen = []

    def runner(prompt, cwd, name, timeout):
        seen.append(Path(cwd))
        (Path(cwd) / "a.py").write_text("changed", encoding="utf-8")
        (Path(cwd) / "new.txt").write_text("n", encoding="utf-8")
        return res(json.dumps(GOOD))

    outs = execute_runs(lab, agent, runner, quick=True)
    assert outs[0].edited_files == ["a.py", "new.txt"]
    assert not seen[0].exists()


def test_runner_exception_becomes_outcome(lab, agent):
    def runner(prompt, cwd, name, timeout):
        raise RuntimeError("kaboom")

    outs = execute_runs(lab, agent, runner, quick=True)
    o = outs[0]
    assert o.error == "kaboom" and not o.passed and o.duration_s == 0.0
    assert not o.timed_out and o.events == [] and o.result_text == ""
    assert o.report.data is None
