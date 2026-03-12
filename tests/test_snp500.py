"""Unit tests for snp500.py — targeting 100% coverage."""

import csv
import importlib
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import snp500


# ── Helpers ────────────────────────────────────────────────────────────────

def _write_csv(path: Path, rows: list[tuple]) -> None:
    """Write a minimal snp500_monthly.csv at *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", "return"])
        for row in rows:
            writer.writerow(row)


# ── default_historical_start ───────────────────────────────────────────────

def test_default_historical_start_is_40_years_ago():
    result = snp500.default_historical_start()
    today = date.today()
    expected_year = today.year - 40
    assert result == f"{expected_year}-{today.month:02d}"


# ── load_monthly_returns ───────────────────────────────────────────────────

def test_load_monthly_returns_reads_csv(tmp_path, monkeypatch):
    cache = tmp_path / "data" / "snp500_monthly.csv"
    _write_csv(cache, [("2000-01", "0.05"), ("2000-02", "-0.03")])
    monkeypatch.setattr(snp500, "_CACHE_FILE", cache)

    result = snp500.load_monthly_returns()
    assert result == {"2000-01": pytest.approx(0.05), "2000-02": pytest.approx(-0.03)}


def test_load_monthly_returns_downloads_when_missing(tmp_path, monkeypatch):
    cache = tmp_path / "data" / "snp500_monthly.csv"
    monkeypatch.setattr(snp500, "_CACHE_FILE", cache)

    def fake_download():
        _write_csv(cache, [("2010-06", "0.01")])

    with patch.object(snp500, "_download_and_cache", side_effect=fake_download):
        result = snp500.load_monthly_returns()

    assert "2010-06" in result


# ── _download_and_cache ────────────────────────────────────────────────────

def test_download_and_cache_raises_without_yfinance(tmp_path, monkeypatch):
    monkeypatch.setattr(snp500, "_CACHE_FILE", tmp_path / "data" / "snp500_monthly.csv")
    with patch.dict("sys.modules", {"yfinance": None}):
        with pytest.raises(RuntimeError, match="yfinance is required"):
            snp500._download_and_cache()


def test_download_and_cache_writes_csv(tmp_path, monkeypatch):
    cache = tmp_path / "data" / "snp500_monthly.csv"
    monkeypatch.setattr(snp500, "_CACHE_FILE", cache)
    monkeypatch.setattr(snp500, "_DATA_DIR", tmp_path / "data")

    # Build a minimal fake yfinance DataFrame
    import pandas as pd

    dates = pd.to_datetime(["2000-01-01", "2000-02-01", "2000-03-01"])
    prices = pd.Series([100.0, 105.0, 102.0], index=dates, name="Close")

    mock_df = MagicMock()
    mock_df.__getitem__ = MagicMock(return_value=prices)

    mock_yf = MagicMock()
    mock_yf.download.return_value = mock_df

    with patch.dict("sys.modules", {"yfinance": mock_yf}):
        snp500._download_and_cache()

    assert cache.exists()
    data = snp500.load_monthly_returns()
    # pct_change drops the first row, so we expect 2 entries
    assert len(data) == 2


# ── build_returns_sequence ─────────────────────────────────────────────────

def _patch_returns(monkeypatch, rows):
    """Patch load_monthly_returns to return *rows* (list of (date_str, float))."""
    monkeypatch.setattr(
        snp500, "load_monthly_returns",
        lambda: {d: r for d, r in rows},
    )


def test_build_returns_sequence_basic(monkeypatch):
    data = [("2000-01", 0.01), ("2000-02", 0.02), ("2000-03", 0.03)]
    _patch_returns(monkeypatch, data)

    result = snp500.build_returns_sequence("2000-01", 3)
    assert result == pytest.approx([0.01, 0.02, 0.03])


def test_build_returns_sequence_start_midway(monkeypatch):
    data = [("2000-01", 0.01), ("2000-02", 0.02), ("2000-03", 0.03)]
    _patch_returns(monkeypatch, data)

    result = snp500.build_returns_sequence("2000-02", 2)
    assert result == pytest.approx([0.02, 0.03])


def test_build_returns_sequence_wraps_cyclically(monkeypatch):
    data = [("2000-01", 0.01), ("2000-02", 0.02), ("2000-03", 0.03)]
    _patch_returns(monkeypatch, data)

    # 5 months starting at index 1 → [0.02, 0.03, 0.01, 0.02, 0.03]
    result = snp500.build_returns_sequence("2000-02", 5)
    assert result == pytest.approx([0.02, 0.03, 0.01, 0.02, 0.03])


def test_build_returns_sequence_falls_back_to_last_if_start_beyond_data(monkeypatch):
    data = [("2000-01", 0.01), ("2000-02", 0.02)]
    _patch_returns(monkeypatch, data)

    # historical_start is beyond available data → falls back to last date
    result = snp500.build_returns_sequence("2099-01", 2)
    # start_idx = last index = 1, so sequence = [0.02, 0.01]
    assert result == pytest.approx([0.02, 0.01])


def test_build_returns_sequence_single_month(monkeypatch):
    data = [("2000-06", 0.05)]
    _patch_returns(monkeypatch, data)

    result = snp500.build_returns_sequence("2000-06", 3)
    assert result == pytest.approx([0.05, 0.05, 0.05])
