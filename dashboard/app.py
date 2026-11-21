"""
Streamlit dashboard for Order-to-Cash monitoring & control.

Run:
    streamlit run dashboard/app.py
"""
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402
from analytics import kpis  # noqa: E402

st.set_page_config(page_title="Auto Parts O2C Dashboard", page_icon="🚚", layout="wide")


@st.cache_data
def get(name: str) -> pd.DataFrame:
    return kpis.run(name)


@st.cache_data
def headline() -> dict:
    return kpis.headline_kpis()


if not cfg.DB_PATH.exists():
    st.error("Database not found. Run `python data/generate_sap_data.py` then `python etl/load_to_db.py`.")
    st.stop()

st.title("🚚 Auto Parts B2B - Order-to-Cash Control Tower")
st.caption(f"Data as of {cfg.AS_OF_DATE} | Synthetic SAP-style data (VBAK, LIKP, VBRK, BSEG)")

# ---------------- KPI tiles
h = headline()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("DSO (days)", f"{h['DSO (days)']:.1f}", f"{h['DSO (days)'] - cfg.DSO_TARGET_DAYS:+.1f} vs target",
          delta_color="inverse")
c2.metric("OTIF %", f"{h['OTIF %']:.1f}%", f"{h['OTIF %'] - cfg.OTIF_TARGET * 100:+.1f} pts vs target")
c3.metric("O2C cycle (days)", f"{h['Order-to-cash cycle (days)']:.1f}")
c4.metric("Open receivables", f"₹{h['Open receivables'] / 1e7:,.1f} Cr")
c5.metric("Overdue", f"₹{h['Overdue (>0 days) receivables'] / 1e7:,.1f} Cr")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📈 Performance", "💰 Receivables", "👥 Customers", "📦 Products", "🤖 At-risk & anomalies"]
)

# ---------------- Performance
with tab1:
    left, right = st.columns(2)
    otif = get("otif_by_month")
    fig = px.line(otif, x="month", y="otif_pct", markers=True, title="OTIF % by month")
    fig.add_hline(y=cfg.OTIF_TARGET * 100, line_dash="dash", annotation_text="Target")
    left.plotly_chart(fig, width="stretch")

    cyc = get("cycle_time").iloc[0]
    stages = pd.DataFrame({
        "Stage": ["Order → Delivery", "Delivery → Invoice", "Invoice → Cash"],
        "Days": [cyc["order_to_delivery_days"], cyc["delivery_to_invoice_days"], cyc["invoice_to_cash_days"]],
    })
    right.plotly_chart(px.bar(stages, x="Stage", y="Days", text="Days", title="Average O2C cycle time by stage"),
                       width="stretch")

    st.subheader("Blocked orders (delivery block set, not yet shipped)")
    st.dataframe(get("blocked_orders"), width="stretch", hide_index=True)

# ---------------- Receivables
with tab2:
    left, right = st.columns(2)
    ageing = get("ageing")
    left.plotly_chart(px.bar(ageing, x="bucket", y="open_amount", text="invoices",
                             title="Receivables ageing (label = # invoices)"), width="stretch")
    rc = get("monthly_revenue_vs_collections").melt("month", var_name="type", value_name="amount")
    right.plotly_chart(px.line(rc, x="month", y="amount", color="type", markers=True,
                               title="Revenue vs collections"), width="stretch")
    st.subheader("Top overdue customers")
    st.dataframe(get("top_overdue_customers"), width="stretch", hide_index=True)

    st.subheader("What-if: cash released by reducing DSO")
    days = st.slider("DSO reduction (days)", 1, 15, 5)
    daily_sales = get("monthly_revenue_vs_collections")["revenue"].tail(6).mean() * 12 / 365
    st.success(f"Reducing DSO by {days} days releases about ₹{daily_sales * days / 1e7:,.2f} Cr of working capital.")

# ---------------- Customers
with tab3:
    pareto = get("customer_pareto")
    left, right = st.columns(2)
    abc = pareto.groupby("abc_class").agg(customers=("customer_id", "count"), revenue=("revenue", "sum")).reset_index()
    left.plotly_chart(px.pie(abc, names="abc_class", values="revenue", title="Revenue by ABC class"),
                      width="stretch")
    right.dataframe(abc, hide_index=True, width="stretch")
    st.subheader("Customer ranking (ABC)")
    st.dataframe(pareto, width="stretch", hide_index=True)
    st.subheader("⚠️ Declining accounts (churn risk)")
    st.dataframe(get("declining_accounts"), width="stretch", hide_index=True)

# ---------------- Products
with tab4:
    cm = get("category_margin")
    left, right = st.columns(2)
    left.plotly_chart(px.bar(cm, x="category", y="margin_pct", text="margin_pct", title="Gross margin % by category"),
                      width="stretch")
    right.plotly_chart(px.bar(get("discount_leakage"), x="customer_type", y="discount_pct",
                              title="Average discount % by customer type"), width="stretch")
    attach = get("accessory_attach_rate").iloc[0, 0]
    st.info(f"Only **{attach}%** of orders include an accessory - a cross-sell opportunity.")
    fc = cfg.REPORT_DIR / "demand_forecast.csv"
    if fc.exists():
        st.subheader("Demand forecast (units, next 3 months)")
        st.dataframe(pd.read_csv(fc).pivot(index="category", columns="month", values="forecast_units"))

# ---------------- AI
with tab5:
    risk = cfg.REPORT_DIR / "open_invoice_risk.csv"
    if risk.exists():
        st.subheader("Open invoices ranked by predicted late-payment exposure")
        st.dataframe(pd.read_csv(risk).head(30), width="stretch", hide_index=True)
    else:
        st.warning("Run `python analytics/late_payment_model.py` to generate predictions.")
    an = cfg.REPORT_DIR / "anomalous_orders.csv"
    if an.exists():
        st.subheader("Anomalous orders (Isolation Forest)")
        st.dataframe(pd.read_csv(an).head(30), width="stretch", hide_index=True)
    else:
        st.warning("Run `python ai/anomaly_detection.py` to generate anomaly flags.")
