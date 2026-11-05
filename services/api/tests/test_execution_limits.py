import pytest

from ai_team.execution_limits import remaining_tokens


def test_remaining_tokens_never_exceeds_authorized_budget():
    assert remaining_tokens(12, 20) == 8
    assert remaining_tokens(30, 20) == 0


@pytest.mark.parametrize("used,limit", [(True, 20), (-1, 20), (1, 0), (1, 1.5)])
def test_invalid_consumption_is_not_a_valid_budget(used, limit):
    with pytest.raises(ValueError):
        remaining_tokens(used, limit)
