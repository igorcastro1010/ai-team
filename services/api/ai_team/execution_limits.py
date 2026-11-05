"""Pure budget arithmetic shared by the private executor."""

MAX_CALLS = 6
MAX_TOKENS = 50000


def remaining_tokens(used: int, limit: int = MAX_TOKENS) -> int:
    if type(used) is not int or type(limit) is not int or used < 0 or limit < 1:
        raise ValueError("Consumo e limite devem ser inteiros válidos")
    return max(0, limit - used)
