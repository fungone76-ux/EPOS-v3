from epos_v3.domain.dice import DiceResult, OutcomeLevel, calculate_pool_size, roll_pool

def test_pool_size_calculation() -> None:
    stats = {"Sarissa": 2, "Dolos": 1}
    pool = calculate_pool_size(stats, ["Sarissa", "Dolos"])
    assert pool == 4

def test_roll_bounds() -> None:
    result = roll_pool(3)
    assert len(result.pool) == 3
    assert all(1 <= d <= 6 for d in result.pool)

def test_critical_failure() -> None:
    result = DiceResult([1, 1, 1], threshold=4)
    assert result.outcome == OutcomeLevel.CRITICAL_FAILURE

def test_full_success() -> None:
    result = DiceResult([4, 5, 2], threshold=4)
    assert result.outcome == OutcomeLevel.FULL_SUCCESS
