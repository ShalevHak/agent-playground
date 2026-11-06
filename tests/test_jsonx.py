from scoring.jsonx import extract_json_object


def test_strict():
    assert extract_json_object('  {"a": 1}\n') == ({"a": 1}, True)


def test_fenced_json():
    text = 'Here:\n```json\n{"a": 2}\n```\nbye'
    assert extract_json_object(text) == ({"a": 2}, False)


def test_fenced_bare():
    assert extract_json_object('x\n```\n{"a": 3}\n```') == ({"a": 3}, False)


def test_fenced_skips_non_dict_fence():
    text = '```python\nprint(1)\n```\n```json\n{"a": 4}\n```'
    assert extract_json_object(text) == ({"a": 4}, False)


def test_prose_wrapped():
    assert extract_json_object('Result: {"a": {"b": 5}} done.') == ({"a": {"b": 5}}, False)


def test_braces_in_strings():
    text = 'ok {"a": "}{ \\" }", "b": 1} tail'
    assert extract_json_object(text) == ({"a": "}{ \" }", "b": 1}, False)


def test_invalid():
    assert extract_json_object('no json {here') == (None, False)


def test_list_is_not_dict():
    assert extract_json_object('[1, 2]') == (None, False)


def test_empty():
    assert extract_json_object('') == (None, False)
    assert extract_json_object('  \n') == (None, False)


def test_first_brace_unparseable_then_later_object():
    assert extract_json_object('{oops} then {"a": 6}') == ({"a": 6}, False)
