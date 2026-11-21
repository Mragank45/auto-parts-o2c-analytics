"""
"Chat with your O2C data": ask a business question, get SQL + answer.

Two modes
    1. LLM mode      - if ANTHROPIC_API_KEY is set, Claude translates the question into SQL.
    2. Offline mode  - otherwise, keyword matching maps the question to a pre-built KPI query.

Safety: the generated SQL is validated (SELECT only) and run on a READ-ONLY connection.

Setup (LLM mode):
    pip install anthropic
    export ANTHROPIC_API_KEY="your-key"        # Windows PowerShell: $env:ANTHROPIC_API_KEY="your-key"

Run:
    python ai/ask_data.py "Which key accounts have the most overdue invoices?"
    python ai/ask_data.py            # interactive mode
"""
import os
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402
from analytics import kpis  # noqa: E402

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

SCHEMA = """
SQLite database. Dates are TEXT in 'YYYY-MM-DD'. Currency is INR.
KNA1(KUNNR customer_id, NAME1 name, ORT01 city, REGIO region, KTOKD customer_type, ZTERM payment_term, KLIMK credit_limit, KEY_ACCOUNT 'Y'/'N')
MARA(MATNR material, MAKTX description, MATKL category, MTART 'Spare Part'/'Accessory', NETPR list_price, STDCOST cost)
VBAK(VBELN sales_order, ERDAT order_date, KUNNR, NETWR order_value, VDATU requested_delivery_date, LIFSK delivery_block, ORDER_STATUS)
VBAP(VBELN sales_order, POSNR, MATNR, KWMENG qty, NETPR, DISCOUNT, NETWR)
LIKP(VBELN delivery, VGBEL sales_order, KUNNR, WADAT_IST goods_issue_date)
LIPS(VBELN delivery, POSNR, VGBEL sales_order, MATNR, LFIMG delivered_qty)
VBRK(VBELN invoice, FKDAT invoice_date, KUNNR, NETWR invoice_value, ZFBDT due_date, VGBEL delivery, SO_VBELN sales_order)
VBRP(VBELN invoice, POSNR, VGBEL, MATNR, FKIMG, NETWR, COST)
BSEG_PAY(BELNR, VBELN invoice, KUNNR, AUGDT payment_date, WRBTR amount, STATUS 'Open'/'Cleared')
Views: v_order_lifecycle (one row per sales order with delivery, invoice and payment info), v_otif (on_time, in_full flags per order).
Use DATE('{as_of}') as today.
"""

OFFLINE_MAP = {
    r"dso|days sales": "dso",
    r"otif|on.?time|in.?full": "otif",
    r"ageing|aging|bucket": "ageing",
    r"overdue|unpaid|collect": "top_overdue_customers",
    r"block": "blocked_orders",
    r"declin|churn|dropp": "declining_accounts",
    r"margin|profit": "category_margin",
    r"discount": "discount_leakage",
    r"accessor|cross.?sell|attach": "accessory_attach_rate",
    r"pareto|abc|top customer|best customer": "customer_pareto",
    r"cycle|how long": "cycle_time",
    r"revenue|collection|sales": "monthly_revenue_vs_collections",
}


def is_safe_select(sql: str) -> bool:
    s = sql.strip().rstrip(";").lower()
    banned = r"\b(insert|update|delete|drop|alter|create|attach|pragma|replace|vacuum)\b"
    return s.startswith(("select", "with")) and ";" not in s and not re.search(banned, s)


def run_sql(sql: str) -> pd.DataFrame:
    # Read-only connection: even a bad query cannot modify data
    con = sqlite3.connect(f"file:{cfg.DB_PATH}?mode=ro", uri=True)
    try:
        return pd.read_sql_query(sql, con)
    finally:
        con.close()


def llm_to_sql(question: str) -> str:
    import anthropic

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=("You are a SQL analyst for an auto-parts Order-to-Cash database. "
                "Return ONE SQLite SELECT statement and nothing else - no markdown, no commentary.\n"
                + SCHEMA.format(as_of=cfg.AS_OF_DATE)),
        messages=[{"role": "user", "content": question}],
    )
    sql = msg.content[0].text.strip()
    return re.sub(r"^```(?:sql)?|```$", "", sql, flags=re.MULTILINE).strip()


def ask(question: str):
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            sql = llm_to_sql(question)
            if not is_safe_select(sql):
                return "Blocked: generated SQL was not a safe SELECT.", sql, None
            return "LLM mode", sql, run_sql(sql)
        except Exception as exc:  # network / API / SQL error -> fall back
            print(f"[LLM mode failed: {exc}] Falling back to offline mode.\n")

    for pattern, name in OFFLINE_MAP.items():
        if re.search(pattern, question.lower()):
            return "Offline mode (keyword match)", f"-- pre-built query: {name}", kpis.run(name)
    return "Offline mode: no match. Try words like DSO, OTIF, overdue, ageing, margin, declining.", "", None


def main():
    questions = [" ".join(sys.argv[1:])] if len(sys.argv) > 1 else None
    while True:
        q = questions.pop() if questions else input("\nAsk about your O2C data (or 'quit'): ").strip()
        if q.lower() in {"quit", "exit", ""}:
            break
        mode, sql, df = ask(q)
        print(f"\n[{mode}]\n{sql}\n")
        if df is not None:
            print(df.head(15).to_string(index=False))
        if len(sys.argv) > 1:
            break


if __name__ == "__main__":
    main()
