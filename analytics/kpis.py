"""
KPI engine: runs the named queries in sql/kpi_queries.sql and returns DataFrames.

Run:
    python analytics/kpis.py
"""
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402

SQL_FILE = cfg.ROOT / "sql" / "kpi_queries.sql"


def load_queries() -> dict:
    """Parse '-- name: xyz' blocks from the SQL file."""
    text = SQL_FILE.read_text(encoding="utf-8")
    parts = re.split(r"^-- name:\s*(\w+)\s*$", text, flags=re.MULTILINE)
    queries = {}
    for name, body in zip(parts[1::2], parts[2::2]):
        lines = [ln for ln in body.splitlines() if not ln.strip().startswith("--")]
        queries[name] = "\n".join(lines).strip().rstrip(";")
    return queries


def run(name: str, as_of: str = cfg.AS_OF_DATE) -> pd.DataFrame:
    queries = load_queries()
    con = sqlite3.connect(cfg.DB_PATH)
    try:
        return pd.read_sql_query(queries[name], con, params={"as_of": as_of})
    finally:
        con.close()


def run_all(as_of: str = cfg.AS_OF_DATE) -> dict:
    return {name: run(name, as_of) for name in load_queries()}


def headline_kpis(as_of: str = cfg.AS_OF_DATE) -> dict:
    otif = run("otif", as_of).iloc[0]
    cyc = run("cycle_time", as_of).iloc[0]
    ageing = run("ageing", as_of)
    return {
        "DSO (days)": float(run("dso", as_of).iloc[0, 0]),
        "OTIF %": float(otif["otif_pct"]),
        "On-time %": float(otif["on_time_pct"]),
        "In-full %": float(otif["in_full_pct"]),
        "Order-to-cash cycle (days)": float(cyc["total_o2c_days"]),
        "Open receivables": float(ageing["open_amount"].sum()),
        "Overdue (>0 days) receivables": float(
            ageing.loc[ageing["bucket"] != "0. Not due", "open_amount"].sum()
        ),
    }


if __name__ == "__main__":
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    print("=== HEADLINE KPIs ===")
    for k, v in headline_kpis().items():
        print(f"{k:<32} {v:>15,.1f}")
    for name, df in run_all().items():
        print(f"\n=== {name} ===")
        print(df.head(10).to_string(index=False))
