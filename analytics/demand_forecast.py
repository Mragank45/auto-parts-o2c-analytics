"""
Forecast monthly demand (units) per part category for the next 3 months.

Method: linear trend + month-of-year seasonality via a simple regression.
Kept intentionally simple and explainable. Swap in Prophet / statsmodels later.

Run:
    python analytics/demand_forecast.py
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402

HORIZON = 3


def monthly_demand() -> pd.DataFrame:
    con = sqlite3.connect(cfg.DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT STRFTIME('%Y-%m-01', so.ERDAT) AS month, m.MATKL AS category, SUM(a.KWMENG) AS units
        FROM VBAP a
        JOIN VBAK so ON so.VBELN = a.VBELN
        JOIN MARA m ON m.MATNR = a.MATNR
        GROUP BY 1, 2
        """,
        con,
        parse_dates=["month"],
    )
    con.close()
    # Drop the current (incomplete) month, if present
    current_month = pd.Timestamp(cfg.AS_OF_DATE).replace(day=1)
    return df[df["month"] < current_month]


def design(months: pd.Series, t0: pd.Timestamp) -> np.ndarray:
    t = ((months.dt.year - t0.year) * 12 + (months.dt.month - t0.month)).to_numpy().reshape(-1, 1)
    season = pd.get_dummies(months.dt.month).reindex(columns=range(1, 13), fill_value=0).to_numpy()
    return np.hstack([t, season])


def main():
    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = monthly_demand()
    t0 = df["month"].min()
    rows = []
    for cat, g in df.groupby("category"):
        g = g.sort_values("month")
        model = Ridge(alpha=1.0).fit(design(g["month"], t0), g["units"])
        fitted = model.predict(design(g["month"], t0))
        mape = float(np.mean(np.abs((g["units"] - fitted) / g["units"])) * 100)
        future = pd.Series(pd.date_range(g["month"].max() + pd.offsets.MonthBegin(1), periods=HORIZON, freq="MS"))
        pred = model.predict(design(future, t0))
        for m, p in zip(future, pred):
            rows.append({"category": cat, "month": m.strftime("%Y-%m"), "forecast_units": int(round(p)),
                         "in_sample_mape_pct": round(mape, 1)})
    out = pd.DataFrame(rows)
    path = cfg.REPORT_DIR / "demand_forecast.csv"
    out.to_csv(path, index=False)
    print(f"Saved {path.relative_to(cfg.ROOT)}")
    print(out.pivot(index="category", columns="month", values="forecast_units").to_string())


if __name__ == "__main__":
    main()
