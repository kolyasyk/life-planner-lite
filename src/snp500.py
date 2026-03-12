"""S&P 500 historical monthly return data loader.

The bundled CSV at data/snp500_monthly.csv is used by default.
If it is missing, the module downloads data once via yfinance and caches it.
"""

import csv
from datetime import date
from pathlib import Path

# Paths are resolved relative to this file: src/snp500.py → project_root/data/
_DATA_DIR  = Path(__file__).parent.parent / "data"
_CACHE_FILE = _DATA_DIR / "snp500_monthly.csv"


def _download_and_cache() -> None:
    """Download S&P 500 monthly price history from Yahoo Finance and write CSV."""
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError(
            "yfinance is required to fetch S&P 500 data. Run: uv add yfinance"
        )

    df = yf.download("^GSPC", start="1927-12-01", interval="1mo",
                     auto_adjust=True, progress=False)

    closes = df["Close"].squeeze()          # handle single or multi-level columns
    returns = closes.pct_change().dropna()

    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "return"])
        for dt, ret in returns.items():
            date_str = dt.strftime("%Y-%m") if hasattr(dt, "strftime") else str(dt)[:7]
            writer.writerow([date_str, f"{float(ret):.8f}"])


def load_monthly_returns() -> dict:
    """Return ``{YYYY-MM: float_return}`` for every available S&P 500 month.

    Downloads and caches the data on first call if the CSV is absent.
    """
    if not _CACHE_FILE.exists():
        _download_and_cache()

    result = {}
    with open(_CACHE_FILE) as f:
        for row in csv.DictReader(f):
            result[row["date"]] = float(row["return"])
    return result


def build_returns_sequence(historical_start: str, num_months: int) -> list:
    """Return a list of *num_months* monthly returns starting at *historical_start*.

    The historical returns are replayed in order from that point.  If the
    simulation runs past the end of available history the sequence wraps
    around cyclically from the beginning of the dataset.

    Args:
        historical_start: ``"YYYY-MM"`` — which historical month maps to
            simulation month 0.
        num_months: total months needed.

    Returns:
        ``list[float]`` of length *num_months*.
    """
    all_returns = load_monthly_returns()
    dates = sorted(all_returns.keys())

    # Find the first date >= historical_start; fall back to the last date.
    start_idx = len(dates) - 1
    for i, d in enumerate(dates):
        if d >= historical_start:
            start_idx = i
            break

    n = len(dates)
    return [all_returns[dates[(start_idx + i) % n]] for i in range(num_months)]


def default_historical_start() -> str:
    """Return the default historical anchor: 40 years before today."""
    today = date.today()
    return f"{today.year - 40}-{today.month:02d}"


if __name__ == "__main__":
    print("Downloading S&P 500 historical data...")
    _download_and_cache()
    data = load_monthly_returns()
    print(f"Saved {len(data)} monthly returns to {_CACHE_FILE}")
    earliest = min(data)
    latest   = max(data)
    print(f"Coverage: {earliest}  to  {latest}")
