import json

from scoring.behavior import ParsedReport, RunOutcome
from scoring.judge import JudgeResult
from scoring.lab import Expected, Lab
from scoring.report import Scorecard, compute_scorecard, render, write_report
from scoring.robustness import RobustnessResult
from scoring.structure import Check, StructureResult


def make_lab(tmp_path):
    return Lab(id="x", root=tmp_path, title="T", agent_name="a", task_prompt="p",
               fixture=tmp_path, expected=Expected("f.py", 1, "c", "f"), variants=[],
               line_tolerance=1, time_budget_s=10, timeout_s=60, consistency_runs=1,
               weights={"structure": 0.2, "behavior": 0.4, "speed": 0.1, "robustness": 0.3})


def struct(score=100.0, checks=None):
    return StructureResult(checks or [], score, True)


def out(run_id="base-1", variant="base", ok=True, dur=5.0, timed_out=False):
    data = {"file": "f.py", "line": 1, "cause": "c", "fix": "f"} if ok else None
    return RunOutcome(run_id, variant, ParsedReport(data, True, None if ok else "no JSON"),
                      ok, ok, [], dur, timed_out, None, "txt",
                      [{"type": "result"}, {"type": "x"}], ok)


def test_scorecard_full(tmp_path):
    lab = make_lab(tmp_path)
    c = compute_scorecard(lab, struct(), [out()], RobustnessResult(100.0, True, 1, 1, False), None)
    assert (c.structure, c.behavior, c.speed, c.robustness, c.total) == (100, 100, 100, 100, 100)


def test_scorecard_judge_blend(tmp_path):
    lab = make_lab(tmp_path)
    j = JudgeResult(50, 100, "c", [], None)
    c = compute_scorecard(lab, struct(), [out()], RobustnessResult(100.0, True, 1, 1, False), j)
    assert c.behavior == 87.5


def test_scorecard_judge_error_falls_back(tmp_path):
    lab = make_lab(tmp_path)
    j = JudgeResult(None, None, "", [], "boom")
    c = compute_scorecard(lab, struct(), [out()], None, j)
    assert c.behavior == 100.0


def test_scorecard_none_dims_renormalize(tmp_path):
    lab = make_lab(tmp_path)
    c = compute_scorecard(lab, struct(50.0), [], None, None)
    assert (c.behavior, c.speed, c.robustness) == (None, None, None)
    assert c.total is None  # no outcomes (gate failed): no total
    # quick: robustness skipped -> weights 0.2/0.4/0.1 renormalized
    c = compute_scorecard(lab, struct(0.0), [out()], RobustnessResult(None, None, 1, 1, True), None)
    assert c.robustness is None and c.total == round(100 * 0.5 / 0.7, 1)


def test_scorecard_speed_mean_and_timeout(tmp_path):
    lab = make_lab(tmp_path)
    c = compute_scorecard(lab, struct(), [out(dur=5), out("v", "moved", dur=99, timed_out=True)],
                          None, None)
    assert c.speed == 50.0


def test_render_ascii_and_lines(tmp_path):
    lab = make_lab(tmp_path)
    st = StructureResult([Check("tools_declared", False, False, "add tools — now")], 80.0, True)
    outs = [out(), out("variant-x", "x", ok=False)]
    j = JudgeResult(100, 90, "nice “work”", ["do more"], None)
    rob = RobustnessResult(50.0, True, 1, 2, False)
    c = compute_scorecard(lab, st, outs, rob, j)
    text = render(lab, c, st, outs, rob, j)
    text.encode("ascii")
    assert "T" in text and "tools_declared" in text and "add tools ? now" in text
    assert "PASS base-1" in text and "f.py:1" in text and "5.0s" in text
    assert "FAIL variant-x" in text and "no JSON" in text
    assert "nice ?work?" in text and "do more" in text


def test_render_judge_unavailable_and_none(tmp_path):
    lab = make_lab(tmp_path)
    c = Scorecard(80.0, None, None, None, 80.0)
    text = render(lab, c, struct(80.0), [], None, JudgeResult(None, None, "", [], "no claude"))
    assert "judge unavailable: no claude" in text
    assert "behavior" in text and "-" in text


def test_write_report_files(tmp_path):
    lab = make_lab(tmp_path)
    outs = [out(), out("variant-x", "x")]
    rob = RobustnessResult(100.0, True, 2, 2, False)
    c = compute_scorecard(lab, struct(), outs, rob, None)
    path = write_report(tmp_path / "r", lab, c, struct(), outs, rob, None)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "report.json" and data["lab"] == "x"
    assert data["scorecard"]["total"] == 100.0 and len(data["runs"]) == 2
    assert "events" not in data["runs"][0] and data["judge"] is None
    lines = (tmp_path / "r" / "transcripts" / "base-1.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x) for x in lines] == [{"type": "result"}, {"type": "x"}]


def test_render_total_dash_without_outcomes(tmp_path):
    lab = make_lab(tmp_path)
    c = compute_scorecard(lab, struct(50.0), [], None, None)
    text = render(lab, c, struct(50.0), [], None, None)
    assert [l for l in text.splitlines() if l.startswith("TOTAL")][0].split() == ["TOTAL", "-"]
    assert "judge" not in text


def test_render_code_only_notes(tmp_path):
    lab = make_lab(tmp_path)
    st = struct()
    outs = [out()]
    c = compute_scorecard(lab, st, outs, None, None)
    skipped = render(lab, c, st, outs, None, None, no_judge=True)
    assert "judge: skipped (--no-judge)" in skipped
    assert "(behavior = code checks only)" in skipped
    err = render(lab, c, st, outs, None, JudgeResult(None, None, "", [], "boom"))
    assert "judge unavailable: boom (behavior = code checks only)" in err
    ok = render(lab, c, st, outs, None, JudgeResult(80, 80, "c", [], None))
    assert "code checks only" not in ok


def tok_out(run_id, inp, outp, cost):
    o = out(run_id)
    o.input_tokens, o.output_tokens, o.cost_usd = inp, outp, cost
    return o


def test_render_and_report_show_tokens(tmp_path):
    lab = make_lab(tmp_path)
    outs = [tok_out("base-1", 12300, 410, 0.02), tok_out("base-2", None, None, None)]
    judge = JudgeResult(100.0, 100.0, "good", [], None, input_tokens=9800, output_tokens=600,
                        cost_usd=0.03)
    c = compute_scorecard(lab, struct(), outs, None, judge)
    text = render(lab, c, struct(), outs, None, judge)
    assert "12.3k in / 410 out" in text
    assert "Tokens: agent 12.3k in / 410 out ($0.02) | judge 9.8k in / 600 out ($0.03)" \
           " | total $0.05" in text
    data = json.loads(write_report(tmp_path / "r", lab, c, struct(), outs, None, judge)
                      .read_text(encoding="utf-8"))
    assert data["tokens"] == {
        "agent": {"input": 12300, "output": 410, "cost_usd": 0.02},
        "judge": {"input": 9800, "output": 600, "cost_usd": 0.03},
        "total_cost_usd": 0.05}
    assert data["runs"][0]["input_tokens"] == 12300
