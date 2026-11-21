"""
ETL: load raw SAP-style CSVs into SQLite and create analytical views.

Run:
    python etl/load_to_db.py
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402

DATE_COLS = {
    "VBAK": ["ERDAT", "VDATU"],
    "LIKP": ["WADAT_IST"],
    "VBRK": ["FKDAT", "ZFBDT"],
    "BSEG_PAY": ["AUGDT"],
}

VIEWS_SQL = f"""
DROP VIEW IF EXISTS v_order_lifecycle;
CREATE VIEW v_order_lifecycle AS
SELECT
    so.VBELN                           AS sales_order,
    so.KUNNR                           AS customer_id,
    c.NAME1                            AS customer_name,
    c.REGIO                            AS region,
    c.KTOKD                            AS customer_type,
    c.KEY_ACCOUNT                      AS key_account,
    c.ZTERM                            AS payment_term,
    so.ERDAT                           AS order_date,
    so.VDATU                           AS requested_date,
    so.LIFSK                           AS delivery_block,
    so.ORDER_STATUS                    AS order_status,
    so.NETWR                           AS order_value,
    dl.VBELN                           AS delivery_no,
    dl.WADAT_IST                       AS goods_issue_date,
    inv.VBELN                          AS invoice_no,
    inv.FKDAT                          AS invoice_date,
    inv.ZFBDT                          AS due_date,
    inv.NETWR                          AS invoice_value,
    p.AUGDT                            AS payment_date,
    p.STATUS                           AS payment_status
FROM VBAK so
JOIN KNA1 c          ON c.KUNNR = so.KUNNR
LEFT JOIN LIKP dl    ON dl.VGBEL = so.VBELN
LEFT JOIN VBRK inv   ON inv.SO_VBELN = so.VBELN
LEFT JOIN BSEG_PAY p ON p.VBELN = inv.VBELN;

DROP VIEW IF EXISTS v_otif;
CREATE VIEW v_otif AS
SELECT
    so.VBELN                                   AS sales_order,
    so.KUNNR                                   AS customer_id,
    so.ERDAT                                   AS order_date,
    so.VDATU                                   AS requested_date,
    dl.WADAT_IST                               AS goods_issue_date,
    CASE WHEN dl.WADAT_IST <= so.VDATU THEN 1 ELSE 0 END AS on_time,
    CASE WHEN q.ordered_qty = q.delivered_qty THEN 1 ELSE 0 END AS in_full
FROM VBAK so
JOIN LIKP dl ON dl.VGBEL = so.VBELN
JOIN (
    SELECT a.VBELN AS so, SUM(a.KWMENG) AS ordered_qty, SUM(b.LFIMG) AS delivered_qty
    FROM VBAP a
    JOIN LIPS b ON b.VGBEL = a.VBELN AND b.POSNR = a.POSNR
    GROUP BY a.VBELN
) q ON q.so = so.VBELN;
"""


def main():
    cfg.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if cfg.DB_PATH.exists():
        cfg.DB_PATH.unlink()

    con = sqlite3.connect(cfg.DB_PATH)
    for csv in sorted(cfg.RAW_DIR.glob("*.csv")):
        name = csv.stem
        df = pd.read_csv(csv, dtype={"KUNNR": str, "VBELN": str, "VGBEL": str,
                                     "SO_VBELN": str, "BELNR": str, "MATNR": str})
        for col in DATE_COLS.get(name, []):
            df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")
        df.to_sql(name, con, index=False, if_exists="replace")
        print(f"Loaded {name:<9} {len(df):>7,} rows")

    # ---- Data quality checks
    cur = con.cursor()
    checks = {
        "Orders without customer": "SELECT COUNT(*) FROM VBAK WHERE KUNNR NOT IN (SELECT KUNNR FROM KNA1)",
        "Invoices without delivery": "SELECT COUNT(*) FROM VBRK WHERE VGBEL NOT IN (SELECT VBELN FROM LIKP)",
        "Negative invoice values": "SELECT COUNT(*) FROM VBRK WHERE NETWR < 0",
        "Duplicate sales orders": "SELECT COUNT(*) - COUNT(DISTINCT VBELN) FROM VBAK",
    }
    print("\nData quality checks")
    for label, sql in checks.items():
        n = cur.execute(sql).fetchone()[0]
        print(f"  {'OK  ' if n == 0 else 'WARN'} {label}: {n}")

    # ---- Indexes + views
    cur.executescript(
        """
        CREATE INDEX IF NOT EXISTS ix_vbak_kunnr ON VBAK(KUNNR);
        CREATE INDEX IF NOT EXISTS ix_likp_vgbel ON LIKP(VGBEL);
        CREATE INDEX IF NOT EXISTS ix_vbrk_so    ON VBRK(SO_VBELN);
        CREATE INDEX IF NOT EXISTS ix_pay_vbeln  ON BSEG_PAY(VBELN);
        """
    )
    cur.executescript(VIEWS_SQL)
    con.commit()
    con.close()
    print(f"\nDatabase ready: {cfg.DB_PATH.relative_to(cfg.ROOT)}")


if __name__ == "__main__":
    main()
