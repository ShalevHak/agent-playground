import json
from pathlib import Path

from scoring.behavior import ParsedReport, RunOutcome
from scoring.claude_cli import ClaudeResult
from scoring.judge import JUDGE_AGENT_FILE, build_judge_input, parse_verdict, run_judge, tool_calls
from scoring.lab import Expected, Lab, Variant

EXP = Expected(file="a.py", line=3, cause="off by one", fix="use <")


def make_lab(tmp_path):
    return Lab(id="x", root=tmp_path, title="T", agent_name="bug-hunter", task_prompt="find it",
               fixture=tmp_path / "fixture", expected=EXP,
               variants=[Variant("v1", None, [], Expected("b.py", 9, "c2", "f2"))],
               line_tolerance=1, time_budget_s=60.0, timeout_s=120.0, consistency_runs=2,
               weights={})


def outcome(run_id="base-1", variant="base", events=None, text="t" * 3000):
    rep = ParsedReport({"file": "a.py", "line": 3, "cause": "c", "fix": "f"}, True, None)
    return RunOutcome(run_id=run_id, variant=variant, report=rep, file_match=True,
                      line_match=True, edited_files=[], duration_s=1.0, timed_out=False,
                      error=None, result_text=text, events=events or [], passed=True)


def tu(name, inp):
    return {"type": "assistant", "message": {"content": [
        {"type": "text", "text": "hi"}, {"type": "tool_use", "name": name, "input": inp}]}}


def test_tool_calls_extracts_and_truncates():
    events = [tu("Read", {"p": "é" * 500}), "junk", {"type": "assistant"},
              {"type": "assistant", "message": {"content": "str"}}, tu("Grep", {"q": "x"})]
    calls = tool_calls(events)
    assert [c["tool"] for c in calls] == ["Read", "Grep"]
    assert len(calls[0]["input"]) == 200
    assert calls[1]["input"] == '{"q": "x"}'


def test_tool_calls_limit():
    assert len(tool_calls([tu("R", {})] * 50)) == 40
    assert len(tool_calls([tu("R", {})] * 5, limit=2)) == 2


def test_build_judge_input_shape(tmp_path):
    lab = make_lab(tmp_path)
    d = build_judge_input(lab, [outcome(events=[tu("Read", {"a": 1})])])
    json.dumps(d)
    assert d["lab"] == {"id": "x", "title": "T", "task_prompt": "find it"}
    assert d["expected"] == {"file": "a.py", "line": 3, "cause": "off by one", "fix": "use <"}
    assert d["variant_expected"]["v1"]["file"] == "b.py"
    assert "agent_definition" not in d and d["agent_definition_file"] == "agent-definition.md"
    r = d["runs"][0]
    assert r["run_id"] == "base-1" and r["variant"] == "base"
    assert r["report"]["line"] == 3 and r["strict_json"] is True
    assert "result_text" not in r
    assert [len(x) for x in r["result_text_lines"]] == [500]
    assert all(len(x) <= 500 for x in r["result_text_lines"])
    assert r["code_checks"] == {"file_match": True, "line_match": True, "edited_files": [],
                                "timed_out": False, "error": None}
    assert r["tool_calls"][0]["tool"] == "Read"


def test_parse_verdict_valid():
    v = parse_verdict('{"cause_score": 80, "fix_score": 60.5, "critique": "c", '
                      '"suggestions": ["a", 1, "b", "c", "d"]}')
    assert (v.cause_score, v.fix_score, v.critique, v.error) == (80, 60.5, "c", None)
    assert v.suggestions == ["a", "b", "c"]


def test_parse_verdict_clamps():
    v = parse_verdict('{"cause_score": 150, "fix_score": -5, "critique": "c"}')
    assert (v.cause_score, v.fix_score, v.suggestions) == (100, 0, [])


def test_parse_verdict_invalid():
    v = parse_verdict('{"cause_score": true, "fix_score": 5, "critique": "keep"}')
    assert v.cause_score is None and v.fix_score is None and v.critique == "keep"
    assert v.error.startswith("invalid judge verdict:")
    assert parse_verdict('{"cause_score": 5}').error.startswith("invalid judge verdict:")
    assert parse_verdict("no json").error.startswith("invalid judge verdict:")


def ok(text, **kw):
    d = dict(result_text=text, events=[], duration_s=1.0, timed_out=False, error=None,
             num_turns=1, cost_usd=0.0)
    d.update(kw)
    return ClaudeResult(**d)


def test_run_judge_sets_up_cwd_and_cleans(tmp_path):
    seen = {}

    def runner(prompt, cwd, agent, timeout):
        seen.update(cwd=cwd, agent=agent, prompt=prompt)
        assert (cwd / ".claude" / "agents" / "judge.md").read_text(encoding="utf-8") == \
            JUDGE_AGENT_FILE.read_text(encoding="utf-8")
        assert (cwd / "agent-definition.md").read_text(encoding="utf-8") == "A"
        return ok('{"cause_score": 70, "fix_score": 90, "critique": "c", "suggestions": []}')

    v = run_judge(make_lab(tmp_path), "A", [outcome()], runner)
    assert v.cause_score == 70 and v.fix_score == 90 and v.error is None
    assert seen["agent"] == "judge" and "judge-input.json" in seen["prompt"]
    assert not seen["cwd"].exists()


def test_run_judge_errors(tmp_path):
    lab = make_lab(tmp_path)
    v = run_judge(lab, "A", [], lambda *a: ok("", error="boom"))
    assert (v.cause_score, v.fix_score, v.critique, v.suggestions, v.error) == (None, None, "", [], "boom")
    assert run_judge(lab, "A", [], lambda *a: ok("", timed_out=True, error="timed out")).error == "timed out"

    def raiser(*a):
        raise RuntimeError("bad")
    assert run_judge(lab, "A", [], raiser).error == "bad"


def test_judge_input_has_no_long_lines(tmp_path):
    seen = {}

    def runner(prompt, cwd, agent, timeout):
        seen["json"] = (cwd / "judge-input.json").read_text(encoding="utf-8")
        seen["md"] = (cwd / "agent-definition.md").read_text(encoding="utf-8")
        return ok('{"cause_score": 1, "fix_score": 1, "critique": "c"}')

    long_text = "x" * 5000 + "\n" + "y" * 5000
    run_judge(make_lab(tmp_path), "A" * 5000, [outcome(text=long_text)], runner)
    assert seen["md"] == "A" * 5000
    assert max(len(l) for l in seen["json"].splitlines()) < 1900


def test_run_judge_records_tokens_and_cost(tmp_path):
    from scoring.claude_cli import ClaudeResult
    verdict = '{"cause_score": 70, "fix_score": 90, "critique": "c", "suggestions": []}'
    r = ClaudeResult(verdict, [], 1.0, False, None, 1, 0.03, input_tokens=900, output_tokens=60)
    v = run_judge(make_lab(tmp_path), "A", [outcome()], lambda *a: r)
    assert (v.input_tokens, v.output_tokens, v.cost_usd) == (900, 60, 0.03)
