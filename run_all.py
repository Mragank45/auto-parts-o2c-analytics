"""
One command to run the whole pipeline:  python run_all.py

Steps: generate data -> load DB -> train models -> anomaly detection -> forecast -> weekly report
Then start the dashboard with:  streamlit run dashboard/app.py
"""
import subprocess
import sys

STEPS = [
    ("Generate synthetic SAP-style data", "data/generate_sap_data.py"),
    ("Load into SQLite + data quality checks", "etl/load_to_db.py"),
    ("Late-payment prediction model", "analytics/late_payment_model.py"),
    ("Anomaly detection", "ai/anomaly_detection.py"),
    ("Demand forecast", "analytics/demand_forecast.py"),
    ("Weekly report + payment reminders", "automation/weekly_report.py"),
]

for i, (label, script) in enumerate(STEPS, 1):
    print(f"\n[{i}/{len(STEPS)}] {label}")
    result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout[-1500:], result.stderr[-1500:])
        sys.exit(f"Step failed: {script}")
    print("    done")

print("\nAll steps complete. Launch the dashboard:  streamlit run dashboard/app.py")
