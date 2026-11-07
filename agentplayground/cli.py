"""agentplayground: learn agentic development one lab at a time.

    agentplayground                 how the playground works
    agentplayground list            available labs
    agentplayground show LAB        read the lab brief
    agentplayground start LAB       create your starter agent file
    agentplayground check LAB       score your agent (--quick for one fast run)
"""
import argparse
import shutil
import sys
from typing import List, Optional

from scoring.claude_cli import Runner
from scoring.lab import LABS_DIR, REPO_ROOT, Lab, LabNotFound, load_lab
from scoring.run import main as run_main

AGENTS_DIR = REPO_ROOT / "workspace" / ".claude" / "agents"

WELCOME = """\
Agent Playground - learn agentic development with Claude Code, one lab at a time.

Each lab gives you a task. You write a Claude Code agent that solves it, and the
playground scores it: a coded checker (structure, behavior, speed, robustness)
plus an LLM judge that critiques your agent's prompt.

How to play:
  1. agentplayground list           see the labs
  2. agentplayground show LAB       read the brief: concept, task, answer format
  3. agentplayground start LAB      create your agent file from a starter template
  4. agentplayground check LAB      score it (add --quick while iterating)
  Edit your agent, check again, repeat until you're happy with the score.
"""


def _agent_file(lab: Lab):
    return AGENTS_DIR / (lab.agent_name + ".md")


def _all_labs() -> List[Lab]:
    dirs = sorted(d for d in LABS_DIR.iterdir() if (d / "lab.yaml").is_file())
    return [load_lab(d.name, LABS_DIR) for d in dirs]


def _print_labs() -> None:
    for lab in _all_labs():
        mark = "[x]" if _agent_file(lab).exists() else "[ ]"
        print("  %s %-7s %s" % (mark, lab.id, lab.title))


def cmd_root() -> int:
    print(WELCOME)
    print("Labs ([x] = agent file exists):")
    _print_labs()
    return 0


def cmd_list() -> int:
    print("Labs ([x] = agent file exists):")
    _print_labs()
    return 0


def cmd_show(lab: Lab) -> int:
    print((lab.root / "README.md").read_text(encoding="utf-8"))
    print("Next: agentplayground start %s" % lab.id)
    return 0


def cmd_start(lab: Lab, force: bool) -> int:
    target = _agent_file(lab)
    if target.exists() and not force:
        print("%s already exists. Edit it, or use --force to reset it to the starter."
              % target.as_posix())
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(lab.root / "starter.md"), str(target))
    print("Created %s" % target.as_posix())
    print("Fill in the TODOs, then: agentplayground check %s --quick" % lab.id)
    return 0


def cmd_check(lab: Lab, quick: bool, runner: Optional[Runner]) -> int:
    target = _agent_file(lab)
    if not target.exists():
        print("No agent file yet. Run: agentplayground start %s" % lab.id)
        return 1
    argv = [lab.id, "--agent-file", str(target)] + (["--quick"] if quick else [])
    return run_main(argv, runner=runner)


def main(argv: Optional[List[str]] = None, runner: Optional[Runner] = None) -> int:
    ap = argparse.ArgumentParser(prog="agentplayground", description=WELCOME,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list", help="available labs")
    for name, text in (("show", "read the lab brief"), ("start", "create your agent file"),
                       ("check", "score your agent")):
        p = sub.add_parser(name, help=text)
        p.add_argument("lab")
        if name == "start":
            p.add_argument("--force", action="store_true", help="overwrite your agent file")
        if name == "check":
            p.add_argument("--quick", action="store_true", help="one fast base run")
    args = ap.parse_args(argv)

    if args.cmd is None:
        return cmd_root()
    if args.cmd == "list":
        return cmd_list()
    try:
        lab = load_lab(args.lab)
    except LabNotFound as exc:
        print(str(exc))
        return 1
    if args.cmd == "show":
        return cmd_show(lab)
    if args.cmd == "start":
        return cmd_start(lab, args.force)
    return cmd_check(lab, args.quick, runner)


if __name__ == "__main__":
    sys.exit(main())
