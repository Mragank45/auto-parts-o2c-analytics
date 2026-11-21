"""
Flag unusual orders/invoices using an Isolation Forest.

Typical business uses: spotting pricing errors, unusually large discounts,
duplicate-looking bulk orders, or orders that deviate from a customer's normal pattern.

Run:
    python ai/anomaly_detection.py
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from sklearn.ensemble import IsolationForest

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402


def detect(contamination: float = 0.02) -> pd.DataFrame:
    con = sqlite3.connect(cfg.DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT so.VBELN AS sales_order, so.KUNNR AS customer_id, c.NAME1 AS customer_name,
               so.ERDAT AS order_date, so.NETWR AS order_value,
               COUNT(a.POSNR) AS n_items,
               SUM(a.KWMENG) AS total_qty,
               AVG(a.DISCOUNT) AS avg_discount,
               MAX(a.KWMENG) AS max_line_qty
        FROM VBAK so
        JOIN VBAP a ON a.VBELN = so.VBELN
        JOIN KNA1 c ON c.KUNNR = so.KUNNR
        GROUP BY so.VBELN
        """,
        con,
    )
    con.close()

    # Compare each order to the customer's own typical order value
    med = df.groupby("customer_id")["order_value"].transform("median")
    df["value_vs_customer_median"] = df["order_value"] / med

    feats = ["order_value", "n_items", "total_qty", "avg_discount", "max_line_qty", "value_vs_customer_median"]
    model = IsolationForest(contamination=contamination, random_state=cfg.SEED)
    df["anomaly_flag"] = model.fit_predict(df[feats]) == -1
    df["anomaly_score"] = -model.score_samples(df[feats])
    return df[df["anomaly_flag"]].sort_values("anomaly_score", ascending=False)


def main():
    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = detect()
    path = cfg.REPORT_DIR / "anomalous_orders.csv"
    out.to_csv(path, index=False)
    print(f"Flagged {len(out)} anomalous orders -> {path.relative_to(cfg.ROOT)}")
    print(out.head(10)[["sales_order", "customer_name", "order_value", "total_qty",
                        "avg_discount", "value_vs_customer_median"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
