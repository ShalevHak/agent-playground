"""Temp workspace builder: fixture copy + variant overlay + agent install."""
import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from scoring.lab import Lab, Variant


def build_workspace(lab: Lab, variant: Optional[Variant], agent_file: Path,
                    parent: Optional[Path] = None) -> Path:
    """Create a temp workspace. The caller deletes it."""
    ws = Path(tempfile.mkdtemp(prefix="pg-", dir=str(parent) if parent else None))
    try:
        shutil.copytree(str(lab.fixture), str(ws), dirs_exist_ok=True) \
            if False else _copy_tree(lab.fixture, ws)
        if variant:
            if variant.overlay:
                _copy_tree(variant.overlay, ws)
            for rel in variant.remove:
                target = ws / rel
                if not target.exists():
                    raise FileNotFoundError(
                        "variant %r removes missing path: %s" % (variant.name, rel))
                if target.is_dir():
                    shutil.rmtree(str(target))
                else:
                    target.unlink()
        dest = ws / ".claude" / "agents" / (lab.agent_name + ".md")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(agent_file), str(dest))
    except BaseException:
        shutil.rmtree(str(ws), ignore_errors=True)
        raise
    return ws


def _copy_tree(src: Path, dst: Path) -> None:
    for p in sorted(src.rglob("*")):
        out = dst / p.relative_to(src)
        if p.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(p), str(out))


def snapshot(ws: Path) -> Dict[str, str]:
    """posix relpath -> sha256 hex; skips anything under .claude/."""
    ws = Path(ws)
    snap = {}
    for p in sorted(ws.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(ws)
        if rel.parts[0] == ".claude":
            continue
        snap[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return snap


def changed_files(before: Dict[str, str], after: Dict[str, str]) -> List[str]:
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))
