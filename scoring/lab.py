"""Lab loader: reads labs/<id>[-slug]/lab.yaml into dataclasses."""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LABS_DIR = REPO_ROOT / "labs"

REQUIRED_KEYS = [
    "id", "title", "agent_name", "task_prompt", "expected", "variants",
    "line_tolerance", "time_budget_s", "timeout_s", "consistency_runs",
    "weights",
]


@dataclass
class Expected:
    file: str
    line: int
    cause: str
    fix: str


@dataclass
class Variant:
    name: str
    overlay: Optional[Path]
    remove: List[str]
    expected: Expected


@dataclass
class Lab:
    id: str
    root: Path
    title: str
    agent_name: str
    task_prompt: str
    fixture: Path
    expected: Expected
    variants: List[Variant]
    line_tolerance: int
    time_budget_s: float
    timeout_s: float
    consistency_runs: int
    weights: Dict[str, float]


class LabNotFound(Exception):
    pass


def _find_lab_dir(lab_id: str, labs_dir: Path) -> Path:
    dirs = sorted(p for p in labs_dir.iterdir() if p.is_dir()) if labs_dir.is_dir() else []
    matches = [p for p in dirs if p.name == lab_id or p.name.startswith(lab_id + "-")]
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(p.name for p in dirs) or "(none)"
    if not matches:
        raise LabNotFound("lab %r not found; available: %s" % (lab_id, available))
    raise LabNotFound("lab %r is ambiguous: %s" % (lab_id, ", ".join(p.name for p in matches)))


def load_lab(lab_id: str, labs_dir: Path = LABS_DIR) -> Lab:
    root = _find_lab_dir(lab_id, Path(labs_dir))
    data = yaml.safe_load((root / "lab.yaml").read_text(encoding="utf-8")) or {}
    for key in REQUIRED_KEYS:
        if key not in data:
            raise ValueError("lab.yaml in %s missing required key: %s" % (root.name, key))
    exp = data["expected"]
    base = Expected(file=exp["file"], line=int(exp["line"]), cause=exp["cause"], fix=exp["fix"])
    variants = []
    for v in data["variants"]:
        vexp = v.get("expected") or {}
        for k in ("file", "line"):
            if k not in vexp:
                raise ValueError("variant %r missing expected.%s" % (v.get("name"), k))
        overlay = v.get("overlay")
        variants.append(Variant(
            name=v["name"],
            overlay=(root / overlay).resolve() if overlay else None,
            remove=list(v.get("remove") or []),
            expected=Expected(
                file=vexp["file"], line=int(vexp["line"]),
                cause=vexp.get("cause", base.cause), fix=vexp.get("fix", base.fix),
            ),
        ))
    return Lab(
        id=data["id"], root=root, title=data["title"], agent_name=data["agent_name"],
        task_prompt=data["task_prompt"], fixture=root / "fixture", expected=base,
        variants=variants, line_tolerance=int(data["line_tolerance"]),
        time_budget_s=float(data["time_budget_s"]), timeout_s=float(data["timeout_s"]),
        consistency_runs=int(data["consistency_runs"]),
        weights={k: float(w) for k, w in data["weights"].items()},
    )
