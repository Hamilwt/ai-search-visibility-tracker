"""Rate limiter tests: pure logic with injected clock, no database."""

from app.api.rate_limit import check_rate_limit, reset_rate_limits


def setup_function() -> None:
    reset_rate_limits()


def teardown_function() -> None:
    reset_rate_limits()


def test_allows_up_to_limit_then_reports_retry_after() -> None:
    for _ in range(5):
        assert check_rate_limit("1.2.3.4", 5, now=1000.0) is None
    assert check_rate_limit("1.2.3.4", 5, now=1000.0) == 3600.0


def test_window_slides() -> None:
    for _ in range(5):
        check_rate_limit("1.2.3.4", 5, now=1000.0)
    assert check_rate_limit("1.2.3.4", 5, now=4600.0) is None


def test_limits_are_per_ip() -> None:
    for _ in range(5):
        check_rate_limit("1.2.3.4", 5, now=1000.0)
    assert check_rate_limit("5.6.7.8", 5, now=1000.0) is None
