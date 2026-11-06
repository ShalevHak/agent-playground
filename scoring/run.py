"""CLI: python -m scoring.run lab01 [--quick] [--agent-file F] [--runs-dir D] [--no-judge]"""
import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from scoring.behavior import execute_runs
from scoring.claude_cli import ClaudeNotAvailable, Runner, find_claude, run_claude
from scoring.judge import run_judge
from scoring.lab import REPO_ROOT, LabNotFound, load_lab
from scoring.report import compute_scorecard, render, write_report
from scoring.robustness import score_robustness
from scoring.structure import check_structure


def _unique_dir(runs_dir: Path) -> Path:
    base = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = runs_dir / base
    n = 2
    while path.exists():
        path = runs_dir / ("%s-%d" % (base, n))
        n += 1
    return path


def main(argv: Optional[List[str]] = None, runner: Optional[Runner] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scoring.run")
    ap.add_argument("lab_id")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--agent-file", default=None)
    ap.add_argument("--runs-dir", default=str(REPO_ROOT / "runs"))
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args(argv)

    try:
        lab = load_lab(args.lab_id)
    except LabNotFound as exc:
        print(str(exc), flush=True)
        return 1

    agent_file = Path(args.agent_file) if args.agent_file else (
        REPO_ROOT / "workspace" / ".claude" / "agents" / (lab.agent_name + ".md"))
    structure = check_structure(agent_file, lab.agent_name)
    if not structure.gate_passed:
        card = compute_scorecard(lab, structure, [], None, None)
        print(render(lab, card, structure, [], None, None), flush=True)
        print("fix the structure errors above before running", flush=True)
        return 2

    if runner is None:
        try:
            cmd = find_claude()
        except ClaudeNotAvailable as exc:
            print(str(exc), flush=True)
            return 3
        runner = lambda prompt, cwd, agent, timeout_s: run_claude(  # noqa: E731
            prompt, cwd, agent, timeout_s, claude_cmd=cmd)

    outcomes = execute_runs(lab, agent_file, runner, quick=args.quick,
                            on_progress=lambda rid: print("running %s..." % rid, flush=True))
    robustness = score_robustness(outcomes, args.quick)
    judge = None
    if not args.no_judge:
        print("running judge...", flush=True)
        judge = run_judge(lab, agent_file.read_text(encoding="utf-8"), outcomes, runner)
    card = compute_scorecard(lab, structure, outcomes, robustness, judge)
    print(render(lab, card, structure, outcomes, robustness, judge), flush=True)
    out_dir = _unique_dir(Path(args.runs_dir))
    path = write_report(out_dir, lab, card, structure, outcomes, robustness, judge,
                        agent_file=agent_file)
    print("report: " + path.as_posix(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
