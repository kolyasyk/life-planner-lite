# Life Planner Lite

A personal financial planning tool that simulates your cash flow month-by-month based on a YAML config file. Visualize income, expenses, investments, and net worth over time — either via CLI chart or an interactive web dashboard.

**Live demo:** https://life-planner-lite.fly.dev

---

## Features

- Define income sources with frequency, growth rate (raises), and start/end dates
- Define expenses with one-time, recurring, or periodic frequencies
- Model investment accounts with compound growth (APR) and monthly contributions
- Set a retirement date — regular income automatically stops and post-retirement income activates
- Interactive web dashboard to edit your plan and see results instantly
- Export/import config as YAML from the browser (no account needed)
- CLI mode for offline use and scripting
- Config persists in browser `localStorage` — the server is fully stateless

---

## Project Structure

```
life_planner_lite/
├── src/
│   ├── app.py          # FastAPI web server + Plotly chart generation
│   └── planner.py      # Core simulation logic (pure Python, no side effects)
├── static/
│   └── index.html      # Single-page web dashboard (Bootstrap 5 + Plotly.js)
├── tests/
│   └── test_planner.py # Unit tests (50 tests, 100% coverage)
├── config.yaml         # Default example configuration
├── Dockerfile          # Container image for deployment
├── fly.toml            # Fly.io deployment config
└── pyproject.toml      # Python dependencies (managed by uv)
```

---

## Quick Start (Local)

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) — Python package manager

### Web Dashboard

```bash
git clone https://github.com/kolyasyk/life-planner-lite.git
cd life-planner-lite
uv sync
uv run python src/app.py
```

Open http://127.0.0.1:8000 in your browser.

### CLI (chart to PNG)

```bash
uv run python src/planner.py               # uses config.yaml
uv run python src/planner.py my_plan.yaml  # custom config file
```

Outputs a `financial_plan.png` chart and a summary to stdout.

---

## Configuration Reference

All plans are defined in a YAML file. Dates are `"YYYY-MM"` strings. Amounts are in your local currency.

### `simulation`

```yaml
simulation:
  start: "2026-01"        # First month to simulate
  end:   "2060-12"        # Last month to simulate
  initial_balance: 15000  # Starting cash balance
```

### `retirement`

```yaml
retirement:
  date: "2050-01"   # Regular income stops here; post-retirement income starts

  income:           # Sources that activate at retirement date
    - name: Social Security
      amount: 2200
      frequency: monthly
```

### `income`

Income items automatically stop at the retirement date unless an explicit `end` is provided.

```yaml
income:
  - name: Primary Salary
    amount: 7000
    frequency: monthly
    start: "2026-01"
    growth_rate: 0.03     # 3% annual raise (optional)

  - name: Annual Bonus
    amount: 8000
    frequency: annual     # paid once per year in the start month
    start: "2026-12"

  - name: Side Project
    amount: 1500
    frequency: monthly
    start: "2026-06"
    end:   "2035-12"      # explicit end overrides retirement cutoff
```

### `expenses`

```yaml
expenses:
  - name: Rent
    amount: 2000
    frequency: monthly
    start: "2026-01"
    end:   "2031-12"

  - name: Home Down Payment
    amount: 50000
    frequency: one-time   # fires exactly once in the start month
    start: "2032-01"

  - name: Annual Vacation
    amount: 4000
    frequency: annual
    start: "2026-07"
```

### `investments`

Monthly contributions are deducted from your cash balance each month. Investment value compounds at `apr` regardless of contribution status.

```yaml
investments:
  - name: 401(k)
    initial_value: 25000
    monthly_contribution: 800
    apr: 0.07             # 7% annual return
    start: "2026-01"
    end:   "2050-01"      # stop contributing at retirement
```

### Supported Frequencies

| Value | Description |
|---|---|
| `monthly` | Every month |
| `biweekly` | Every two weeks (26× per year) |
| `weekly` | Every week (52× per year) |
| `quarterly` | Every 3 months from the start date |
| `annual` / `yearly` | Once per year in the same calendar month as `start` |
| `one-time` | Once only, in the `start` month |

---

## Web Dashboard

The dashboard loads your config on first visit, then stores changes in browser `localStorage` (no server writes needed).

| Button | Action |
|---|---|
| **▶ Run** | Re-runs the simulation and updates the chart |
| **💾 Save** | Persists current plan to `localStorage` |
| **⬇ Export** | Downloads your plan as `config.yaml` |
| **⬆ Import** | Loads a `config.yaml` file and re-runs |

The chart shows two panels:
- **Wealth over time** — cash balance, investment value, and net worth
- **Monthly cash flows** — income vs expenses per month

---

## Running Tests

```bash
uv run pytest tests/ --cov=planner --cov-report=term-missing
```

50 unit tests covering all simulation logic with 100% code coverage.

---

## Deployment

The app is stateless (no file writes at runtime) and deploys to any container platform.

### Fly.io

```bash
# First deploy
fly launch

# Redeploy after changes
fly deploy
```

Config is set in `fly.toml`. The app runs on a shared-cpu-1x instance with 256 MB RAM and auto-stops when idle (free tier friendly).

### Docker

```bash
docker build -t life-planner-lite .
docker run -p 8080:8080 life-planner-lite
```

---

## Development

```bash
# Install all dependencies including dev tools
uv sync --all-groups

# Run the web server with auto-reload
PYTHONPATH=src uv run uvicorn app:app --reload

# Run tests
uv run pytest tests/

# Run tests with coverage
uv run pytest tests/ --cov=planner --cov-report=term-missing
```
