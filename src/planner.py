#!/usr/bin/env python3
"""Life Planner Lite - Monthly financial simulation from a YAML config."""

import sys
import yaml
from datetime import date


# ---------------------------------------------------------------------------
# Date helpers (year-month tuples, no external deps)
# ---------------------------------------------------------------------------

def parse_ym(value):
    """Parse 'YYYY-MM' string to (year, month) tuple, or return None."""
    if value is None:
        return None
    parts = str(value).split("-")
    return (int(parts[0]), int(parts[1]))


def ym_to_date(ym):
    return date(ym[0], ym[1], 1)


def ym_add(ym, months):
    y, m = ym
    m += months
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return (y, m)


def ym_diff_months(a, b):
    """How many months from a to b (can be negative)."""
    return (b[0] - a[0]) * 12 + (b[1] - a[1])


# ---------------------------------------------------------------------------
# Cash-flow helpers
# ---------------------------------------------------------------------------

def is_active(item, ym):
    start = parse_ym(item.get("start"))
    end = parse_ym(item.get("end"))
    if start and ym < start:
        return False
    if end and ym > end:
        return False
    return True


def get_monthly_cash(item, ym):
    """Return the cash-flow amount for *item* in the given month *ym*.

    Supported frequencies: monthly, biweekly, weekly, quarterly, annual /
    yearly, one-time.  Amounts grow continuously at *growth_rate* (annual).
    """
    if not is_active(item, ym):
        return 0.0

    freq = str(item.get("frequency", "monthly")).lower()
    amount = float(item["amount"])

    # Apply annual growth rate (compounded from start)
    growth_rate = float(item.get("growth_rate", 0))
    start = parse_ym(item.get("start"))
    if growth_rate and start:
        years_elapsed = ym_diff_months(start, ym) / 12
        amount *= (1 + growth_rate) ** years_elapsed

    start_month = start[1] if start else 1
    y, m = ym

    if freq == "monthly":
        return amount

    elif freq == "weekly":
        return amount * 52 / 12

    elif freq == "biweekly":
        return amount * 26 / 12

    elif freq in ("annual", "yearly"):
        # Fire once per year in the same calendar month as the start
        return amount if m == start_month else 0.0

    elif freq == "quarterly":
        # Fire every 3 months from start
        months_since = ym_diff_months(start, ym) if start else 0
        return amount if months_since % 3 == 0 else 0.0

    elif freq == "one-time":
        return amount if (start and ym == start) else 0.0

    # Unknown frequency: treat as monthly
    return amount


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------

def simulate(config):
    sim = config.get("simulation", {})
    start_ym = parse_ym(sim.get("start", "2026-01"))
    end_ym   = parse_ym(sim.get("end",   "2055-12"))
    balance  = float(sim.get("initial_balance", 0))

    retirement_cfg    = config.get("retirement", {})
    retirement_ym     = parse_ym(retirement_cfg.get("date"))
    retirement_income = retirement_cfg.get("income", [])

    incomes     = config.get("income", [])
    expenses    = config.get("expenses", [])
    investments = config.get("investments", [])

    # --- S&P 500 historical returns (loaded only if at least one investment needs it) ---
    snp_returns = None
    if any(inv.get("use_snp500") for inv in investments):
        from snp500 import build_returns_sequence, default_historical_start
        snp500_cfg      = config.get("snp500") or {}
        historical_start = snp500_cfg.get("historical_start") or default_historical_start()
        n_months        = ym_diff_months(start_ym, end_ym) + 1
        snp_returns     = build_returns_sequence(historical_start, n_months)

    # Track current value of each investment account separately
    inv_values = [float(inv.get("initial_value", 0)) for inv in investments]

    months        = []
    balances      = []
    net_worths    = []
    inv_totals    = []
    all_incomes   = []
    all_expenses  = []

    month_idx = 0
    ym = start_ym
    while ym <= end_ym:
        # --- Income ---
        monthly_income = 0.0

        for item in incomes:
            effective = dict(item)
            # If there's a retirement date and the item has no explicit end,
            # stop regular income at retirement.
            if retirement_ym and item.get("end") is None:
                effective["end"] = f"{retirement_ym[0]}-{retirement_ym[1]:02d}"
            monthly_income += get_monthly_cash(effective, ym)

        # Post-retirement income sources
        if retirement_ym and ym >= retirement_ym:
            for item in retirement_income:
                monthly_income += get_monthly_cash(item, ym)

        # --- Expenses ---
        monthly_expenses = sum(get_monthly_cash(exp, ym) for exp in expenses)

        # --- Investments: grow then contribute ---
        total_inv = 0.0
        for i, inv in enumerate(investments):
            if inv.get("use_snp500") and snp_returns is not None:
                monthly_rate = snp_returns[month_idx]
            else:
                monthly_rate = (1 + float(inv.get("apr", 0))) ** (1 / 12) - 1
            inv_values[i] *= (1 + monthly_rate)            # compound growth
            if is_active(inv, ym):
                contrib = float(inv.get("monthly_contribution", 0))
                inv_values[i]    += contrib
                monthly_expenses += contrib                # funded from cash
            total_inv += inv_values[i]

        balance += monthly_income - monthly_expenses

        months.append(ym_to_date(ym))
        balances.append(balance)
        inv_totals.append(total_inv)
        net_worths.append(balance + total_inv)
        all_incomes.append(monthly_income)
        all_expenses.append(monthly_expenses)

        month_idx += 1
        ym = ym_add(ym, 1)

    return months, balances, inv_totals, net_worths, all_incomes, all_expenses


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def plot(months, balances, inv_totals, net_worths, all_incomes, all_expenses,
         retirement_date=None):
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.ticker as mticker
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})

    def k(vals):
        return [v / 1_000 for v in vals]

    # --- Top panel: wealth ---
    ax1.plot(months, k(balances),   label="Cash balance",               linewidth=2)
    ax1.plot(months, k(inv_totals), label="Investments",                linewidth=2, linestyle="--")
    ax1.plot(months, k(net_worths), label="Net worth (cash + invest.)",  linewidth=2, linestyle=":")
    ax1.axhline(y=0, color="black", linewidth=0.8)
    ax1.set_ylabel("Amount ($000s)")
    ax1.set_title("Financial Plan")
    ax1.grid(True, alpha=0.3)
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}k"))

    # --- Bottom panel: monthly cash flows ---
    ax2.plot(months, k(all_incomes),  label="Monthly income",   linewidth=1.5, color="green")
    ax2.plot(months, k(all_expenses), label="Monthly expenses", linewidth=1.5, color="tomato")
    ax2.axhline(y=0, color="black", linewidth=0.8)
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Monthly ($000s)")
    ax2.grid(True, alpha=0.3)
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}k"))

    # Retirement line on both panels
    if retirement_date:
        rd = ym_to_date(parse_ym(retirement_date))
        for ax in (ax1, ax2):
            ax.axvline(x=rd, color="red", linestyle="-.", linewidth=1.5,
                       label=f"Retirement ({retirement_date})")

    ax1.legend(loc="upper left")
    ax2.legend(loc="upper left")

    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.xaxis.set_major_locator(mdates.YearLocator(2))
    plt.xticks(rotation=45)

    plt.tight_layout()
    out = "financial_plan.png"
    plt.savefig(out, dpi=150)
    print(f"Chart saved to {out}")
    plt.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    months, balances, inv_totals, net_worths, all_incomes, all_expenses = simulate(config)

    retirement_date = config.get("retirement", {}).get("date")
    plot(months, balances, inv_totals, net_worths, all_incomes, all_expenses, retirement_date)

    print(f"\nSimulation period : {months[0]}  to  {months[-1]}")
    print(f"Starting balance  : ${balances[0]:>14,.0f}")
    print(f"Final cash balance: ${balances[-1]:>14,.0f}")
    print(f"Final investments : ${inv_totals[-1]:>14,.0f}")
    print(f"Final net worth   : ${net_worths[-1]:>14,.0f}")


if __name__ == "__main__":
    main()
