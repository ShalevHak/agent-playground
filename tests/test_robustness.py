from scoring.behavior import ParsedReport, RunOutcome
from scoring.robustness import score_robustness


def _o(rid, passed, file="a.py", line=1):
    data = {"file": file, "line": line, "cause": "c", "fix": "f"}
    return RunOutcome(run_id=rid, variant="base", report=ParsedReport(data, True, None),
                      file_match=passed, line_match=passed, edited_files=[], duration_s=1.0,
                      timed_out=False, error=None, result_text="", events=[], passed=passed)


def test_quick_skipped():
    r = score_robustness([_o("base-1", True)], quick=True)
    assert r.skipped and r.score is None and r.consistent is None


def test_all_pass_consistent():
    r = score_robustness([_o("base-1", True), _o("base-2", True), _o("variant-x", True)], False)
    assert r.score == 100 and r.consistent is True
    assert r.passed_runs == 3 and r.total_runs == 3 and not r.skipped


def test_partial_and_inconsistent():
    r = score_robustness([_o("base-1", True), _o("base-2", True, line=2), _o("variant-x", False)], False)
    assert r.passed_runs == 2 and r.total_runs == 3
    assert abs(r.score - 200 / 3) < 1e-9
    assert r.consistent is False


def test_failed_base_not_consistent():
    r = score_robustness([_o("base-1", True), _o("base-2", False)], False)
    assert r.consistent is False


def test_empty():
    r = score_robustness([], False)
    assert r.score == 0.0 and r.total_runs == 0 and r.consistent is False
