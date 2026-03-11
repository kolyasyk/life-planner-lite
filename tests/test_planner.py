"""Unit tests for planner.py — targeting 100% coverage."""

import sys
from datetime import date
from unittest.mock import patch

import matplotlib
import pytest

matplotlib.use("Agg")  # must be set before any pyplot import

from planner import (
    get_monthly_cash,
    is_active,
    main,
    parse_ym,
    plot,
    simulate,
    ym_add,
    ym_diff_months,
    ym_to_date,
)


# ── parse_ym ──────────────────────────────────────────────────────────────

def test_parse_ym_none():
    assert parse_ym(None) is None

def test_parse_ym_string():
    assert parse_ym("2026-01") == (2026, 1)

def test_parse_ym_december():
    assert parse_ym("2030-12") == (2030, 12)


# ── ym_to_date ────────────────────────────────────────────────────────────

def test_ym_to_date():
    assert ym_to_date((2026, 3)) == date(2026, 3, 1)


# ── ym_add ────────────────────────────────────────────────────────────────

def test_ym_add_no_overflow():
    assert ym_add((2026, 6), 1) == (2026, 7)

def test_ym_add_year_overflow():
    assert ym_add((2026, 12), 1) == (2027, 1)

def test_ym_add_multi_month_overflow():
    assert ym_add((2026, 11), 3) == (2027, 2)


# ── ym_diff_months ────────────────────────────────────────────────────────

def test_ym_diff_same():
    assert ym_diff_months((2026, 1), (2026, 1)) == 0

def test_ym_diff_forward():
    assert ym_diff_months((2026, 1), (2027, 1)) == 12

def test_ym_diff_backward():
    assert ym_diff_months((2027, 1), (2026, 1)) == -12

def test_ym_diff_partial():
    assert ym_diff_months((2026, 3), (2026, 8)) == 5


# ── is_active ─────────────────────────────────────────────────────────────

def test_is_active_no_dates():
    assert is_active({}, (2026, 6)) is True

def test_is_active_before_start():
    assert is_active({"start": "2026-06"}, (2026, 1)) is False

def test_is_active_at_start():
    assert is_active({"start": "2026-01"}, (2026, 1)) is True

def test_is_active_after_end():
    assert is_active({"end": "2026-06"}, (2026, 7)) is False

def test_is_active_at_end():
    assert is_active({"end": "2026-06"}, (2026, 6)) is True

def test_is_active_in_range():
    assert is_active({"start": "2026-01", "end": "2026-12"}, (2026, 6)) is True

def test_is_active_only_start_far_future():
    assert is_active({"start": "2026-01"}, (2030, 1)) is True

def test_is_active_only_end_far_future():
    assert is_active({"end": "2030-12"}, (2026, 1)) is True


# ── get_monthly_cash ──────────────────────────────────────────────────────

def test_cash_inactive():
    item = {"amount": 1000, "frequency": "monthly", "start": "2026-06"}
    assert get_monthly_cash(item, (2026, 1)) == 0.0

def test_cash_monthly():
    assert get_monthly_cash({"amount": 1000, "frequency": "monthly"}, (2026, 1)) == 1000.0

def test_cash_weekly():
    result = get_monthly_cash({"amount": 100, "frequency": "weekly"}, (2026, 1))
    assert result == pytest.approx(100 * 52 / 12)

def test_cash_biweekly():
    result = get_monthly_cash({"amount": 100, "frequency": "biweekly"}, (2026, 1))
    assert result == pytest.approx(100 * 26 / 12)

def test_cash_annual_matching_month():
    item = {"amount": 1200, "frequency": "annual", "start": "2026-03"}
    assert get_monthly_cash(item, (2026, 3)) == pytest.approx(1200.0)

def test_cash_annual_non_matching_month():
    item = {"amount": 1200, "frequency": "annual", "start": "2026-03"}
    assert get_monthly_cash(item, (2026, 4)) == 0.0

def test_cash_yearly_alias():
    item = {"amount": 1200, "frequency": "yearly", "start": "2026-03"}
    assert get_monthly_cash(item, (2026, 3)) == pytest.approx(1200.0)

def test_cash_annual_no_start_fires_in_january():
    # No start → start_month defaults to 1
    item = {"amount": 500, "frequency": "annual"}
    assert get_monthly_cash(item, (2026, 1)) == pytest.approx(500.0)
    assert get_monthly_cash(item, (2026, 2)) == 0.0

def test_cash_quarterly_match():
    # 3 months since start → 3 % 3 == 0 → fires
    item = {"amount": 500, "frequency": "quarterly", "start": "2026-01"}
    assert get_monthly_cash(item, (2026, 4)) == pytest.approx(500.0)

def test_cash_quarterly_no_match():
    # 1 month since start → 1 % 3 != 0 → silent
    item = {"amount": 500, "frequency": "quarterly", "start": "2026-01"}
    assert get_monthly_cash(item, (2026, 2)) == 0.0

def test_cash_quarterly_no_start():
    # No start → months_since = 0 → 0 % 3 == 0 → fires
    item = {"amount": 500, "frequency": "quarterly"}
    assert get_monthly_cash(item, (2026, 1)) == pytest.approx(500.0)

def test_cash_one_time_match():
    item = {"amount": 5000, "frequency": "one-time", "start": "2026-06"}
    assert get_monthly_cash(item, (2026, 6)) == 5000.0

def test_cash_one_time_non_match():
    item = {"amount": 5000, "frequency": "one-time", "start": "2026-06"}
    assert get_monthly_cash(item, (2026, 7)) == 0.0

def test_cash_one_time_no_start():
    # No start → always 0
    item = {"amount": 5000, "frequency": "one-time"}
    assert get_monthly_cash(item, (2026, 6)) == 0.0

def test_cash_unknown_frequency_treated_as_monthly():
    item = {"amount": 1000, "frequency": "daily"}
    assert get_monthly_cash(item, (2026, 1)) == pytest.approx(1000.0)

def test_cash_with_growth_rate():
    # After 12 months at 12% annual growth → amount * 1.12
    item = {"amount": 1000, "frequency": "monthly", "start": "2026-01", "growth_rate": 0.12}
    result = get_monthly_cash(item, (2027, 1))
    assert result == pytest.approx(1000 * 1.12)

def test_cash_growth_rate_without_start_not_applied():
    # growth_rate set but no start → condition `growth_rate and start` is False → no growth
    item = {"amount": 1000, "frequency": "monthly", "growth_rate": 0.12}
    assert get_monthly_cash(item, (2027, 1)) == pytest.approx(1000.0)


# ── simulate ──────────────────────────────────────────────────────────────

def test_simulate_minimal_no_cashflows():
    config = {"simulation": {"start": "2026-01", "end": "2026-03", "initial_balance": 500}}
    months, balances, inv_totals, net_worths, incomes, expenses = simulate(config)
    assert len(months) == 3
    assert months[0] == date(2026, 1, 1)
    assert all(b == pytest.approx(500.0) for b in balances)
    assert all(i == pytest.approx(0.0) for i in inv_totals)

def test_simulate_default_dates():
    # No simulation section → defaults used
    months, *_ = simulate({})
    assert months[0] == date(2026, 1, 1)
    assert months[-1] == date(2055, 12, 1)

def test_simulate_income_and_expense():
    config = {
        "simulation": {"start": "2026-01", "end": "2026-02", "initial_balance": 0},
        "income":   [{"amount": 3000, "frequency": "monthly"}],
        "expenses": [{"amount": 1000, "frequency": "monthly"}],
    }
    _, balances, *_ = simulate(config)
    assert balances[0] == pytest.approx(2000.0)
    assert balances[1] == pytest.approx(4000.0)

def test_simulate_income_stops_at_retirement():
    # Income with no explicit end is cut off at retirement date
    config = {
        "simulation": {"start": "2026-01", "end": "2026-03"},
        "income":     [{"amount": 1000, "frequency": "monthly"}],
        "retirement": {"date": "2026-02"},
    }
    _, balances, *_ = simulate(config)
    assert balances[0] == pytest.approx(1000.0)   # Jan: income active
    assert balances[1] == pytest.approx(2000.0)   # Feb: income active (end is inclusive)
    assert balances[2] == pytest.approx(2000.0)   # Mar: income stopped

def test_simulate_income_explicit_end_not_overridden_by_retirement():
    # Income with an explicit end date keeps that end, even if retirement is later
    config = {
        "simulation": {"start": "2026-01", "end": "2026-04"},
        "income":     [{"amount": 200, "frequency": "monthly", "end": "2026-02"}],
        "retirement": {"date": "2026-03"},
    }
    _, balances, *_ = simulate(config)
    assert balances[0] == pytest.approx(200.0)
    assert balances[1] == pytest.approx(400.0)
    assert balances[2] == pytest.approx(400.0)   # income ended in Feb
    assert balances[3] == pytest.approx(400.0)

def test_simulate_retirement_income_activates():
    config = {
        "simulation": {"start": "2026-01", "end": "2026-03"},
        "retirement": {
            "date": "2026-02",
            "income": [{"amount": 500, "frequency": "monthly"}],
        },
    }
    _, balances, *_ = simulate(config)
    assert balances[0] == pytest.approx(0.0)     # Jan: no income
    assert balances[1] == pytest.approx(500.0)   # Feb: pension starts
    assert balances[2] == pytest.approx(1000.0)  # Mar: pension continues

def test_simulate_no_retirement_section():
    # retirement_ym is None → neither retirement branch fires
    config = {
        "simulation": {"start": "2026-01", "end": "2026-01"},
        "income": [{"amount": 800, "frequency": "monthly"}],
    }
    _, balances, *_ = simulate(config)
    assert balances[0] == pytest.approx(800.0)

def test_simulate_investment_growth_and_contribution():
    config = {
        "simulation": {"start": "2026-01", "end": "2026-01", "initial_balance": 1000},
        "investments": [{
            "name": "401k",
            "initial_value": 0,
            "monthly_contribution": 500,
            "apr": 0.0,
            "start": "2026-01",
        }],
    }
    _, balances, inv_totals, *_ = simulate(config)
    assert inv_totals[0] == pytest.approx(500.0)
    assert balances[0] == pytest.approx(500.0)   # 1000 initial − 500 contribution

def test_simulate_investment_compound_growth():
    apr = 0.12
    config = {
        "simulation": {"start": "2026-01", "end": "2026-01"},
        "investments": [{"initial_value": 12000, "monthly_contribution": 0, "apr": apr}],
    }
    _, _, inv_totals, *_ = simulate(config)
    expected = 12000 * ((1 + apr) ** (1 / 12))
    assert inv_totals[0] == pytest.approx(expected)

def test_simulate_investment_inactive_no_contribution():
    # Investment whose active period has already ended — value grows but no new contributions
    config = {
        "simulation": {"start": "2026-03", "end": "2026-03", "initial_balance": 0},
        "investments": [{
            "initial_value": 1000,
            "monthly_contribution": 500,
            "apr": 0.0,
            "start": "2026-01",
            "end": "2026-02",
        }],
    }
    _, balances, inv_totals, *_ = simulate(config)
    assert inv_totals[0] == pytest.approx(1000.0)  # no contribution added
    assert balances[0] == pytest.approx(0.0)        # nothing deducted from cash


# ── plot ──────────────────────────────────────────────────────────────────

def _plot_args():
    months = [date(2026, 1, 1), date(2026, 2, 1)]
    vals   = [1000.0, 2000.0]
    return months, vals, vals, vals, vals, vals


def test_plot_without_retirement():
    with patch("matplotlib.pyplot.savefig"), \
         patch("matplotlib.pyplot.show"), \
         patch("builtins.print"):
        plot(*_plot_args())


def test_plot_with_retirement():
    with patch("matplotlib.pyplot.savefig"), \
         patch("matplotlib.pyplot.show"), \
         patch("builtins.print"):
        plot(*_plot_args(), retirement_date="2026-01")


# ── main ──────────────────────────────────────────────────────────────────

_FAKE_SIMULATE_RETURN = (
    [date(2026, 1, 1), date(2026, 2, 1)],
    [1000.0, 2000.0],
    [500.0, 600.0],
    [1500.0, 2600.0],
    [1000.0, 1000.0],
    [0.0, 0.0],
)


def test_main_uses_default_config_path(tmp_path, monkeypatch):
    import yaml
    cfg = tmp_path / "config.yaml"
    cfg.write_text(yaml.dump({"retirement": {"date": "2050-01"}}))
    monkeypatch.setattr(sys, "argv", ["planner.py"])
    monkeypatch.chdir(tmp_path)
    with patch("planner.simulate", return_value=_FAKE_SIMULATE_RETURN), \
         patch("planner.plot"), \
         patch("builtins.print"):
        main()


def test_main_uses_custom_config_path(tmp_path, monkeypatch):
    import yaml
    cfg = tmp_path / "custom.yaml"
    cfg.write_text(yaml.dump({"simulation": {"start": "2026-01", "end": "2026-02"}}))
    monkeypatch.setattr(sys, "argv", ["planner.py", str(cfg)])
    with patch("planner.simulate", return_value=_FAKE_SIMULATE_RETURN), \
         patch("planner.plot"), \
         patch("builtins.print"):
        main()
