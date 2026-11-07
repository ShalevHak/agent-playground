import pytest

from scoring.speed import speed_score


def test_within_budget():
    assert speed_score(10, 60) == 100
    assert speed_score(60, 60) == 100


def test_linear_decay():
    assert speed_score(120, 60) == pytest.approx(50.0)


def test_zero_at_triple():
    assert speed_score(180, 60) == 0
    assert speed_score(500, 60) == 0


def test_timed_out_is_zero():
    assert speed_score(1, 60, timed_out=True) == 0
