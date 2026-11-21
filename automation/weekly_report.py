"""
Automated weekly O2C report.

Produces:
    reports/weekly_o2c_report_<date>.xlsx   (KPI summary, ageing, overdue accounts,
                                             blocked orders, at-risk invoices, declining accounts)
    reports/payment_reminders_<date>.txt    (ready-to-send reminder emails for overdue key accounts)

Run manually:
    python automation/weekly_report.py

Run automatically every Monday 8:00 (Linux/Mac cron):
    0 8 * * 1 cd /path/to/auto-parts-o2c-analytics && python automation/weekly_report.py
Windows: use Task Scheduler. Or use the GitHub Actions workflow in .github/workflows/weekly_report.yml.
"""
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402
from analytics import kpis  # noqa: E402

REMINDER_TEMPLATE = """\
To: accounts@{domain}
Subject: Payment reminder - {n} overdue invoice(s) totalling INR {amount:,.0f}

Dear {name} team,

Our records show {n} invoice(s) past their due date, totalling INR {amount:,.0f}.
The oldest invoice is {days:.0f} days overdue.

Please arrange payment at your earliest convenience, or let us know if there is a
dispute or missing document holding up the payment.

Regards,
Key Account Coordination Team
{sep}
"""


def style_workbook(path: Path):
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = load_workbook(path)
    for ws in wb.worksheets:
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F3864")
            cell.alignment = Alignment(horizontal="center")
        for col in ws.columns:
            width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
            ws.column_dimensions[col[0].column_letter].width = min(width + 3, 45)
        ws.freeze_panes = "A2"
    wb.save(path)


def main():
    cfg.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = cfg.AS_OF_DATE
    q = kpis.run_all()
    head = kpis.headline_kpis()

    # KPI summary with RAG status against targets
    rows = []
    for k, v in head.items():
        status = ""
        if k == "OTIF %":
            status = "GREEN" if v >= cfg.OTIF_TARGET * 100 else ("AMBER" if v >= 85 else "RED")
        if k == "DSO (days)":
            status = "GREEN" if v <= cfg.DSO_TARGET_DAYS else ("AMBER" if v <= cfg.DSO_TARGET_DAYS + 10 else "RED")
        rows.append({"KPI": k, "Value": round(v, 1), "Status": status})
    summary = pd.DataFrame(rows)

    risk_path = cfg.REPORT_DIR / "open_invoice_risk.csv"
    risk = pd.read_csv(risk_path).head(25) if risk_path.exists() else pd.DataFrame()

    xlsx = cfg.REPORT_DIR / f"weekly_o2c_report_{stamp}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="KPI Summary", index=False)
        q["ageing"].to_excel(xw, sheet_name="Receivables Ageing", index=False)
        q["top_overdue_customers"].to_excel(xw, sheet_name="Overdue Accounts", index=False)
        q["blocked_orders"].to_excel(xw, sheet_name="Blocked Orders", index=False)
        q["declining_accounts"].to_excel(xw, sheet_name="Declining Accounts", index=False)
        q["otif_by_month"].to_excel(xw, sheet_name="OTIF Trend", index=False)
        if not risk.empty:
            risk.to_excel(xw, sheet_name="At-Risk Invoices", index=False)
    style_workbook(xlsx)
    print(f"Report  -> {xlsx.relative_to(cfg.ROOT)}")

    # Payment reminders for overdue accounts above a threshold
    overdue = q["top_overdue_customers"]
    overdue = overdue[overdue["max_days_overdue"] >= cfg.OVERDUE_ALERT_DAYS]
    txt = cfg.REPORT_DIR / f"payment_reminders_{stamp}.txt"
    with open(txt, "w", encoding="utf-8") as f:
        for _, r in overdue.iterrows():
            domain = "".join(ch for ch in r["customer_name"].lower() if ch.isalnum())[:20] + ".example.com"
            f.write(REMINDER_TEMPLATE.format(
                domain=domain, n=r["overdue_invoices"], amount=r["overdue_amount"],
                name=r["customer_name"], days=r["max_days_overdue"], sep="=" * 60))
    print(f"Reminders -> {txt.relative_to(cfg.ROOT)}  ({len(overdue)} customers)")

    print("\nKPI summary")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
