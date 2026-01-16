from autocoder.agent.agent import _auto_continue_delay_from_rate_limit, AUTO_CONTINUE_DELAY_SECONDS


def test_auto_continue_delay_defaults_when_not_limit_reached():
    delay, target = _auto_continue_delay_from_rate_limit("All good")
    assert delay == float(AUTO_CONTINUE_DELAY_SECONDS)
    assert target is None


def test_auto_continue_delay_parses_reset_time_when_available():
    delay, target = _auto_continue_delay_from_rate_limit("Limit reached. Resets 11:59pm (UTC)")
    assert delay >= 0.0
    assert delay <= 24 * 60 * 60
    # If tzdata isn't available, target may be None; in that case the delay should fall back.
    if target is None:
        assert delay == float(AUTO_CONTINUE_DELAY_SECONDS)
    else:
        assert "UTC" in target

