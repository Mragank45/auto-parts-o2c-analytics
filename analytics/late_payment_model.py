"""
Predict which invoices will be paid late, and rank open invoices for collections.

Approach
    - Training set : invoices already cleared (label = paid after due date)
    - Features     : amount, payment term, customer type/region/key account,
                     customer's historical late-rate (computed only from PAST invoices
                     to avoid data leakage), invoice month, days to deliver
    - Model        : Gradient Boosting Classifier (scikit-learn)
    - Output       : reports/open_invoice_risk.csv  (open invoices with late probability)

Run:
    python analytics/late_payment_model.py
"""
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402


def load_invoices() -> pd.DataFrame:
    con = sqlite3.connect(cfg.DB_PATH)
    df = pd.read_sql_query(
        """
        SELECT inv.VBELN AS invoice_no, inv.KUNNR AS customer_id, inv.FKDAT AS invoice_date,
               inv.ZFBDT AS due_date, inv.NETWR AS amount,
               c.ZTERM AS payment_term, c.KTOKD AS customer_type, c.REGIO AS region,
               c.KEY_ACCOUNT AS key_account, c.NAME1 AS customer_name,
               p.AUGDT AS payment_date, p.STATUS AS status,
               JULIANDAY(dl.WADAT_IST) - JULIANDAY(so.ERDAT) AS order_to_delivery_days
        FROM VBRK inv
        JOIN KNA1 c ON c.KUNNR = inv.KUNNR
        JOIN BSEG_PAY p ON p.VBELN = inv.VBELN
        JOIN LIKP dl ON dl.VBELN = inv.VGBEL
        JOIN VBAK so ON so.VBELN = inv.SO_VBELN
        """,
        con,
        parse_dates=["invoice_date", "due_date", "payment_date"],
    )
    con.close()
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("invoice_date").reset_index(drop=True)
    as_of = pd.Timestamp(cfg.AS_OF_DATE)

    # Label: late if cleared after due date. Open invoices past due are also late.
    df["is_late"] = np.where(
        df["payment_date"].notna(),
        (df["payment_date"] > df["due_date"]).astype(int),
        np.where(df["due_date"] < as_of, 1, np.nan),
    )

    # Customer's historical late rate using only invoices CLEARED BEFORE this invoice was raised
    hist_rate = []
    for _, row in df.iterrows():
        past = df[
            (df["customer_id"] == row["customer_id"])
            & (df["payment_date"].notna())
            & (df["payment_date"] < row["invoice_date"])
        ]
        hist_rate.append(past["is_late"].mean() if len(past) >= 3 else np.nan)
    df["cust_hist_late_rate"] = hist_rate
    df["cust_hist_late_rate"] = df["cust_hist_late_rate"].fillna(df["cust_hist_late_rate"].mean())

    df["term_days"] = df["payment_term"].str[1:].astype(int)
    df["log_amount"] = np.log1p(df["amount"])
    df["inv_month"] = df["invoice_date"].dt.month
    df["key_account_flag"] = (df["key_account"] == "Y").astype(int)
    df = pd.get_dummies(df, columns=["customer_type", "region"], drop_first=True)
    return df


FEATURE_PREFIXES = ("log_amount", "term_days", "inv_month", "key_account_flag",
                    "order_to_delivery_days", "cust_hist_late_rate", "customer_type_", "region_")


def main():
    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_invoices()
    df = add_features(raw)
    feats = [c for c in df.columns if c.startswith(FEATURE_PREFIXES)]

    # Train on cleared invoices only (true labels), predict on open ones
    train_df = df[df["payment_date"].notna()].copy()
    open_df = df[df["payment_date"].isna()].copy()

    # Time-based split: train on older invoices, test on the newest 20%
    train_df = train_df.sort_values("invoice_date")
    cut = int(len(train_df) * 0.8)
    X_tr, y_tr = train_df.iloc[:cut][feats], train_df.iloc[:cut]["is_late"]
    X_te, y_te = train_df.iloc[cut:][feats], train_df.iloc[cut:]["is_late"]

    model = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, random_state=cfg.SEED)
    model.fit(X_tr, y_tr)
    proba = model.predict_proba(X_te)[:, 1]
    print(f"Hold-out ROC-AUC: {roc_auc_score(y_te, proba):.3f}")
    print(classification_report(y_te, (proba >= 0.5).astype(int), target_names=["On time", "Late"]))

    imp = pd.Series(model.feature_importances_, index=feats).sort_values(ascending=False)
    print("Top drivers of late payment:")
    print(imp.head(6).round(3).to_string())

    # Score open invoices
    model.fit(train_df[feats], train_df["is_late"])
    open_df["late_probability"] = model.predict_proba(open_df[feats])[:, 1]
    out = open_df.merge(raw[["invoice_no", "customer_name"]].drop_duplicates(), on="invoice_no", how="left",
                        suffixes=("_x", ""))
    out["expected_loss_exposure"] = (out["amount"] * out["late_probability"]).round(0)
    cols = ["invoice_no", "customer_id", "customer_name", "invoice_date", "due_date", "amount",
            "late_probability", "expected_loss_exposure"]
    out = out[cols].sort_values("expected_loss_exposure", ascending=False)
    out["late_probability"] = out["late_probability"].round(3)

    path = cfg.REPORT_DIR / "open_invoice_risk.csv"
    out.to_csv(path, index=False)
    print(f"\nScored {len(out)} open invoices -> {path.relative_to(cfg.ROOT)}")
    print(out.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
