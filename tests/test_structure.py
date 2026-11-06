from pathlib import Path

from scoring.structure import check_structure

ROOT = Path(__file__).resolve().parent.parent
SOLUTION = ROOT / "labs" / "lab01-contract" / "solution" / "bug-hunter.md"
SLOPPY = ROOT / "tests" / "agents" / "sloppy.md"

GOOD_BODY = (
    "Return JSON with file, line, cause and fix. Stop when you found the cause.\n"
)


def write(tmp_path, text):
    p = tmp_path / "a.md"
    p.write_text(text, encoding="utf-8")
    return p


def by_id(res):
    return {c.id: c for c in res.checks}


def agent(name="bug-hunter", tools="tools: Read, Grep", desc="description: x",
          body=GOOD_BODY):
    lines = ["---", "name: " + name, desc, tools, "---", body]
    return "\n".join(l for l in lines if l)


def test_check_order():
    res = check_structure(SOLUTION, "bug-hunter")
    assert [c.id for c in res.checks] == [
        "exists", "frontmatter", "name_matches", "description",
        "tools_declared", "read_only_tools", "output_schema", "json_only",
        "stopping_rule"]
    crit = [c.id for c in res.checks if c.critical]
    assert crit == ["exists", "frontmatter", "name_matches", "read_only_tools"]


def test_solution_passes_all():
    res = check_structure(SOLUTION, "bug-hunter")
    assert all(c.passed for c in res.checks), [c.id for c in res.checks if not c.passed]
    assert res.score == 100
    assert res.gate_passed
    assert all(c.hint == "" for c in res.checks)


def test_sloppy_passes_gate_fails_quality():
    res = check_structure(SLOPPY, "bug-hunter")
    failed = {c.id for c in res.checks if not c.passed}
    assert failed == {"output_schema", "json_only", "stopping_rule"}
    assert res.gate_passed
    assert abs(res.score - 100 * 6 / 9) < 1e-9
    assert all(c.hint for c in res.checks if not c.passed)


def test_missing_file(tmp_path):
    res = check_structure(tmp_path / "nope.md", "bug-hunter")
    r = by_id(res)
    assert not r["exists"].passed
    assert not res.gate_passed
    assert res.score == 0
    for cid in ("frontmatter", "name_matches", "description", "read_only_tools"):
        assert not r[cid].passed
        assert r[cid].hint == "fix the earlier error first"


def test_no_frontmatter(tmp_path):
    res = check_structure(write(tmp_path, "just text JSON"), "bug-hunter")
    r = by_id(res)
    assert r["exists"].passed
    assert not r["frontmatter"].passed
    assert r["name_matches"].hint == "fix the earlier error first"
    assert not res.gate_passed


def test_bad_yaml_and_non_dict(tmp_path):
    for text in ("---\nname: [unclosed\n---\nbody", "---\n- a\n- b\n---\nbody"):
        res = check_structure(write(tmp_path, text), "bug-hunter")
        assert not by_id(res)["frontmatter"].passed
        assert not res.gate_passed


def test_wrong_name(tmp_path):
    res = check_structure(write(tmp_path, agent(name="other")), "bug-hunter")
    r = by_id(res)
    assert not r["name_matches"].passed
    assert not res.gate_passed
    assert "bug-hunter" in r["name_matches"].hint


def test_non_string_name_and_description(tmp_path):
    text = "---\nname: 5\ndescription: [a]\ntools: Read\n---\nbody"
    r = by_id(check_structure(write(tmp_path, text), "5"))
    assert not r["name_matches"].passed
    assert not r["description"].passed


def test_edit_tool_not_read_only(tmp_path):
    res = check_structure(write(tmp_path, agent(tools="tools: Read, Edit")), "bug-hunter")
    r = by_id(res)
    assert r["tools_declared"].passed
    assert not r["read_only_tools"].passed
    assert "Edit" in r["read_only_tools"].hint
    assert not res.gate_passed


def test_bash_pattern_not_read_only(tmp_path):
    res = check_structure(write(tmp_path, agent(tools="tools: Read, Bash(git:*)")), "bug-hunter")
    assert not by_id(res)["read_only_tools"].passed


def test_list_form_tools(tmp_path):
    res = check_structure(write(tmp_path, agent(tools="tools: [Read, Grep, Glob]")), "bug-hunter")
    r = by_id(res)
    assert r["tools_declared"].passed and r["read_only_tools"].passed
    assert res.score == 100


def test_yaml_block_list_tools(tmp_path):
    res = check_structure(write(tmp_path, agent(tools="tools:\n  - Read\n  - Grep")), "bug-hunter")
    assert by_id(res)["read_only_tools"].passed


def test_string_tools_whitespace_and_empty_entries(tmp_path):
    res = check_structure(write(tmp_path, agent(tools="tools: ' Read ,, Grep , '")), "bug-hunter")
    assert by_id(res)["read_only_tools"].passed


def test_tools_missing_or_empty(tmp_path):
    for tools in ("", "tools: ''", "tools: []"):
        r = by_id(check_structure(write(tmp_path, agent(tools=tools)), "bug-hunter"))
        assert not r["tools_declared"].passed
        assert not r["read_only_tools"].passed
        assert r["read_only_tools"].critical


def test_empty_description(tmp_path):
    r = by_id(check_structure(write(tmp_path, agent(desc="description: ''")), "bug-hunter"))
    assert not r["description"].passed


def test_body_is_after_closing_frontmatter(tmp_path):
    # words in the frontmatter must not count toward body checks
    text = ("---\nname: bug-hunter\ndescription: file line cause fix JSON stop\n"
            "tools: Read\n---\nnothing here\n")
    r = by_id(check_structure(write(tmp_path, text), "bug-hunter"))
    assert not r["output_schema"].passed
    assert not r["json_only"].passed
    assert not r["stopping_rule"].passed


def test_schema_word_match_is_whole_word_case_insensitive(tmp_path):
    ok = by_id(check_structure(write(tmp_path, agent(body="FILE, Line, CAUSE, fix. json")), "bug-hunter"))
    assert ok["output_schema"].passed and ok["json_only"].passed
    bad = by_id(check_structure(write(tmp_path, agent(body="files, lines, causes, fixes")), "bug-hunter"))
    assert not bad["output_schema"].passed


def test_stopping_phrases(tmp_path):
    for phrase in ("Stop now.", "You are done when it works", "finished when ok",
                   "finish when ok", "As soon as you know"):
        r = by_id(check_structure(write(tmp_path, agent(body=phrase)), "bug-hunter"))
        assert r["stopping_rule"].passed, phrase
    r = by_id(check_structure(write(tmp_path, agent(body="stoppage nonstop")), "bug-hunter"))
    assert not r["stopping_rule"].passed


def test_yaml_value_error_fails_frontmatter_without_crash(tmp_path):
    res = check_structure(write(tmp_path, agent(desc="description: 2026-02-30")), "bug-hunter")
    assert not by_id(res)["frontmatter"].passed
