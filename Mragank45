# 🚚 Auto Parts B2B — Order-to-Cash Analytics & Automation

An end-to-end Business Analyst portfolio project for a B2B auto parts & accessories distributor.
It follows the full **Order-to-Payment** cycle in SAP terms, measures it with KPIs, finds
improvement opportunities, automates reporting, and adds ML/AI on top.

> **Note:** all data is **synthetic**, generated to mirror real SAP SD/FI table and field names
> (VBAK, VBAP, LIKP, VBRK, BSEG…). No real company data is used.

## Key findings (from the generated dataset)

| Area | Finding |
|---|---|
| **Delivery performance** | OTIF is **74.7%** vs a 95% target. Delivery timeliness (83.1% on-time) is a bigger problem than short shipments (89.9% in-full). |
| **Cash collection** | DSO is **48.8 days** vs a 45-day target. Invoice-to-cash takes 52.5 of the 58.1 days in the O2C cycle, so collections is the main lever, not fulfilment. |
| **Overdue concentration** | ₹5.9 Cr is overdue. **The top 5 customers hold 51%** of it, and 4 of the 5 are key accounts. 35% of overdue value is 90+ days old. |
| **Working capital** | Cutting DSO by 5 days would release roughly **₹1.9 Cr** of cash. |
| **Sales growth** | Only **30.7%** of orders include an accessory, which is a cross-sell opportunity. |
| **Customer base** | 35 of 60 customers make up 80% of revenue (ABC class A). Declining accounts are flagged as churn risks. |
| **ML** | The late-payment model reaches **ROC-AUC ≈ 0.83**; the customer's past payment behaviour is the strongest predictor. |

## JD → project mapping

| Role requirement | Where it is covered |
|---|---|
| Key account coordination, order to payment | `v_order_lifecycle` view, key-account flag, overdue-account tracking |
| Customer satisfaction, sales increase, cost optimisation | OTIF analysis, accessory cross-sell, discount leakage, category margin |
| Process improvement / automation | `automation/weekly_report.py`, auto-generated payment reminders, GitHub Actions schedule |
| KPI monitoring & control | `sql/kpi_queries.sql`, Streamlit dashboard with targets (see `docs/kpi_definitions.md`) |
| Project management | `docs/BRD.md`, roadmap and stakeholder map |
| Business & customer acumen | ABC customer segmentation, churn-risk (declining) accounts |
| Financial acumen | Receivables ageing, revenue vs collections, DSO what-if (working capital) |
| Data analytics & AI usability | Late-payment prediction, anomaly detection, demand forecast, natural-language Q&A |
| SAP hands-on | SAP-style tables and T-codes, see the table below |
| Cross-functional collaboration | Stakeholder map and user stories in `docs/BRD.md` |

## SAP mapping

| Table | Meaning | T-code |
|---|---|---|
| KNA1 | Customer master | XD03 |
| MARA | Material master | MM03 |
| VBAK / VBAP | Sales order header / item | VA01 / VA03 |
| LIKP / LIPS | Delivery header / item | VL01N / VL03N |
| VBRK / VBRP | Billing document header / item | VF01 / VF03 |
| BSEG_PAY | Customer line items (simplified BSID/BSAD) | FBL5N |

## Project structure

```
auto-parts-o2c-analytics/
├── config.py                  # dates, targets, thresholds
├── run_all.py                 # runs the whole pipeline
├── data/generate_sap_data.py  # synthetic SAP-style data generator
├── etl/load_to_db.py          # CSV -> SQLite, data-quality checks, views
├── sql/kpi_queries.sql        # DSO, OTIF, ageing, ABC, margin, ...
├── analytics/
│   ├── kpis.py                # runs the SQL KPIs
│   ├── late_payment_model.py  # ML: predicts late-paying invoices
│   └── demand_forecast.py     # units forecast per part category
├── ai/
│   ├── anomaly_detection.py   # Isolation Forest on orders
│   └── ask_data.py            # ask questions in plain English (LLM or offline)
├── automation/weekly_report.py  # Excel report + reminder emails
├── dashboard/app.py           # Streamlit dashboard
├── docs/                      # BRD, KPI definitions, process flow
└── .github/workflows/         # scheduled weekly run
```

## Quick start

```bash
git clone https://github.com/<your-username>/auto-parts-o2c-analytics.git
cd auto-parts-o2c-analytics
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run_all.py                  # builds data, DB, models, reports (~20 s)
streamlit run dashboard/app.py     # opens the dashboard
```

Ask questions in plain English:

```bash
python ai/ask_data.py "Which key accounts have the most overdue invoices?"
```

Without an API key it uses keyword matching. To enable LLM mode, set `ANTHROPIC_API_KEY`.

## Recommendations (what a BA would propose)

1. **Collections:** start a dunning cycle at due date minus 5 days for the top 15 accounts, which hold most of the overdue value. Escalate any 90+ day items to sales heads.
2. **Delivery:** investigate the on-time gap. Release delivery blocks within 24 hours and set a daily blocked-order review.
3. **Credit control:** use the late-payment score to set credit holds and shorter terms for high-risk accounts.
4. **Growth:** bundle accessories with spare-part orders for the 69% of orders that don't contain one.
5. **Retention:** hold account reviews with the declining customers before they churn.

## Tech stack

Python · pandas · SQLite · scikit-learn · Streamlit · Plotly · openpyxl · GitHub Actions · (optional) Claude API
