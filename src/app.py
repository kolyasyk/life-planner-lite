#!/usr/bin/env python3
"""Life Planner Lite — web dashboard (FastAPI + Plotly)."""

import json
from pathlib import Path

import yaml
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from planner import simulate

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

CONFIG_PATH = Path("config.yaml")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/config")
async def get_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}



@app.post("/api/simulate")
async def run_simulation(request: Request):
    config = await request.json()

    try:
        months, balances, inv_totals, net_worths, all_incomes, all_expenses = simulate(config)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    xs = [d.strftime("%Y-%m-01") for d in months]
    retirement_date = (config.get("retirement") or {}).get("date")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.08,
        subplot_titles=("Wealth Over Time", "Monthly Cash Flows"),
    )

    fig.add_trace(go.Scatter(
        x=xs, y=balances, name="Cash Balance",
        line=dict(color="#4e79a7", width=2),
        hovertemplate="$%{y:,.0f}<extra>Cash Balance</extra>",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=xs, y=inv_totals, name="Investments",
        line=dict(color="#f28e2b", width=2, dash="dash"),
        hovertemplate="$%{y:,.0f}<extra>Investments</extra>",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=xs, y=net_worths, name="Net Worth",
        line=dict(color="#59a14f", width=2.5),
        fill="tozeroy", fillcolor="rgba(89,161,79,0.06)",
        hovertemplate="$%{y:,.0f}<extra>Net Worth</extra>",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=xs, y=all_incomes, name="Income",
        line=dict(color="#59a14f", width=1.5),
        hovertemplate="$%{y:,.0f}<extra>Income</extra>",
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=xs, y=all_expenses, name="Expenses",
        line=dict(color="#e15759", width=1.5),
        hovertemplate="$%{y:,.0f}<extra>Expenses</extra>",
    ), row=2, col=1)

    if retirement_date:
        rd_str = str(retirement_date) + "-01"
        fig.add_shape(
            type="line",
            x0=rd_str, x1=rd_str,
            y0=0, y1=1,
            xref="x", yref="paper",
            line=dict(color="red", width=1.5, dash="dash"),
        )
        fig.add_annotation(
            x=rd_str, xref="x",
            y=0.67, yref="paper",
            text=f"Retirement<br>{retirement_date}",
            showarrow=False, xanchor="left",
            bgcolor="rgba(255,255,255,0.85)",
            bordercolor="red", borderwidth=1,
            font=dict(color="red", size=10),
        )

    fig.update_yaxes(tickprefix="$", tickformat=",.0f")
    fig.update_layout(
        height=620,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=80, r=30, t=60, b=20),
        paper_bgcolor="white",
        plot_bgcolor="#f9f9f9",
    )

    summary = {
        "period_start": str(months[0].year),
        "period_end": str(months[-1].year),
        "final_cash": balances[-1],
        "final_investments": inv_totals[-1],
        "final_net_worth": net_worths[-1],
    }

    return JSONResponse({"figure": json.loads(fig.to_json()), "summary": summary})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
