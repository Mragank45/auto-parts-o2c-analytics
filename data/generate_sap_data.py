"""
Generate a synthetic, SAP-style Order-to-Cash dataset for an auto parts distributor.

Tables (named after real SAP tables):
    KNA1  - Customer master
    MARA  - Material master (parts & accessories)
    VBAK  - Sales order header          (T-code VA01)
    VBAP  - Sales order item
    LIKP  - Delivery header             (T-code VL01N)
    LIPS  - Delivery item
    VBRK  - Billing (invoice) header    (T-code VF01)
    VBRP  - Billing item
    BSEG_PAY - Customer payments / clearing (simplified BSAD / BSID, T-code FBL5N)

Run:
    python data/generate_sap_data.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as cfg  # noqa: E402

rng = np.random.default_rng(cfg.SEED)
fake = Faker("en_IN")
Faker.seed(cfg.SEED)

AS_OF = pd.Timestamp(cfg.AS_OF_DATE)

REGIONS = ["North", "South", "East", "West"]
CUSTOMER_TYPES = ["Authorized Dealer", "Multi-brand Workshop", "Fleet Operator", "Distributor"]
PAYMENT_TERMS = {"Z030": 30, "Z045": 45, "Z060": 60}

CATEGORIES = {
    "Engine Parts": (800, 18000),
    "Brake System": (400, 9000),
    "Filters": (150, 1800),
    "Electricals": (300, 12000),
    "Suspension": (900, 15000),
    "Body Parts": (700, 22000),
    "Accessories": (200, 8000),
    "Lubricants": (250, 3500),
}


def make_customers() -> pd.DataFrame:
    rows = []
    for i in range(cfg.N_CUSTOMERS):
        term = rng.choice(list(PAYMENT_TERMS), p=[0.3, 0.45, 0.25])
        ctype = rng.choice(CUSTOMER_TYPES, p=[0.4, 0.3, 0.15, 0.15])
        # Each customer has a hidden "payment behaviour" used later by the ML model
        behaviour = rng.choice(["good", "average", "poor"], p=[0.45, 0.35, 0.20])
        rows.append(
            {
                "KUNNR": f"{1000000 + i}",
                "NAME1": fake.company(),
                "ORT01": fake.city(),
                "REGIO": rng.choice(REGIONS),
                "KTOKD": ctype,
                "ZTERM": term,
                "KLIMK": int(rng.choice([500000, 1000000, 2500000, 5000000])),
                "KEY_ACCOUNT": "Y" if rng.random() < 0.2 else "N",
                "PAY_BEHAVIOUR": behaviour,  # synthetic only; not a real SAP field
            }
        )
    return pd.DataFrame(rows)


def make_materials() -> pd.DataFrame:
    rows = []
    cats = list(CATEGORIES)
    for i in range(cfg.N_MATERIALS):
        cat = cats[i % len(cats)]
        lo, hi = CATEGORIES[cat]
        price = round(float(rng.uniform(lo, hi)), 2)
        rows.append(
            {
                "MATNR": f"MAT{100000 + i}",
                "MAKTX": f"{cat} - {fake.bothify('??-####').upper()}",
                "MATKL": cat,
                "MTART": "Accessory" if cat == "Accessories" else "Spare Part",
                "NETPR": price,
                "STDCOST": round(price * float(rng.uniform(0.55, 0.8)), 2),
            }
        )
    return pd.DataFrame(rows)


def build_orders(customers: pd.DataFrame, materials: pd.DataFrame):
    dates = pd.date_range(cfg.START_DATE, cfg.END_DATE, freq="D")
    # Customers have different order frequencies (key accounts order more)
    weights = np.where(customers["KEY_ACCOUNT"] == "Y", 4.0, 1.0)
    weights = weights / weights.sum()

    vbak, vbap, likp, lips, vbrk, vbrp, pay = [], [], [], [], [], [], []

    for n in range(cfg.N_ORDERS):
        cust = customers.iloc[rng.choice(len(customers), p=weights)]
        order_date = pd.Timestamp(rng.choice(dates))
        vbeln = f"{5000000 + n}"

        # ---- Order items
        n_items = int(rng.integers(1, 6))
        mats = materials.sample(n_items, random_state=int(rng.integers(0, 1_000_000)))
        order_value = 0.0
        items = []
        for pos, (_, m) in enumerate(mats.iterrows(), start=1):
            qty = int(rng.integers(5, 80))
            disc = float(rng.choice([0, 0, 0.02, 0.05, 0.08]))
            net = round(qty * m["NETPR"] * (1 - disc), 2)
            order_value += net
            items.append((pos, m["MATNR"], qty, m["NETPR"], disc, net, m["STDCOST"]))
            vbap.append(
                {
                    "VBELN": vbeln,
                    "POSNR": pos * 10,
                    "MATNR": m["MATNR"],
                    "KWMENG": qty,
                    "NETPR": m["NETPR"],
                    "DISCOUNT": disc,
                    "NETWR": net,
                }
            )

        requested = order_date + pd.Timedelta(days=int(rng.integers(3, 10)))
        blocked = rng.random() < 0.03
        vbak.append(
            {
                "VBELN": vbeln,
                "ERDAT": order_date,
                "KUNNR": cust["KUNNR"],
                "NETWR": round(order_value, 2),
                "VDATU": requested,  # requested delivery date
                "LIFSK": "01" if blocked else "",  # delivery block
                "ORDER_STATUS": "Open",
            }
        )

        # ---- Delivery (some orders are cancelled / never delivered)
        if rng.random() < 0.02:
            vbak[-1]["ORDER_STATUS"] = "Cancelled"
            continue

        # Delay depends on customer type; key accounts get better service
        base_delay = rng.poisson(1.5 if cust["KEY_ACCOUNT"] == "Y" else 2.5)
        block_delay = int(rng.integers(3, 8)) if blocked else 0
        gi_date = order_date + pd.Timedelta(days=int(2 + base_delay + block_delay))
        if gi_date > AS_OF:
            vbak[-1]["ORDER_STATUS"] = "In Process"
            continue

        likp_id = f"{8000000 + n}"
        delivered_qty = []
        for pos, matnr, qty, price, disc, net, cost in items:
            # Short shipments create "in-full" failures
            short = rng.random() < 0.035
            delivered = int(qty * rng.uniform(0.6, 0.95)) if short else qty
            delivered_qty.append(delivered)
            lips.append(
                {
                    "VBELN": likp_id,
                    "POSNR": pos * 10,
                    "VGBEL": vbeln,
                    "MATNR": matnr,
                    "LFIMG": delivered,
                }
            )
        likp.append(
            {
                "VBELN": likp_id,
                "VGBEL": vbeln,
                "KUNNR": cust["KUNNR"],
                "WADAT_IST": gi_date,  # actual goods issue date
            }
        )

        # ---- Invoice (1-3 days after delivery)
        inv_date = gi_date + pd.Timedelta(days=int(rng.integers(0, 4)))
        if inv_date > AS_OF:
            continue
        vbrk_id = f"{9000000 + n}"
        inv_value = 0.0
        for item, dq in zip(items, delivered_qty):
            pos, matnr, qty, price, disc, net, cost = item
            billed_net = round(dq * price * (1 - disc), 2)
            inv_value += billed_net
            vbrp.append(
                {
                    "VBELN": vbrk_id,
                    "POSNR": pos * 10,
                    "VGBEL": likp_id,
                    "MATNR": matnr,
                    "FKIMG": dq,
                    "NETWR": billed_net,
                    "COST": round(dq * cost, 2),
                }
            )
        inv_value = round(inv_value, 2)
        term_days = PAYMENT_TERMS[cust["ZTERM"]]
        due_date = inv_date + pd.Timedelta(days=term_days)
        vbrk.append(
            {
                "VBELN": vbrk_id,
                "FKDAT": inv_date,
                "KUNNR": cust["KUNNR"],
                "NETWR": inv_value,
                "ZFBDT": due_date,
                "VGBEL": likp_id,
                "SO_VBELN": vbeln,
            }
        )

        # ---- Payment: depends on customer behaviour
        behaviour = cust["PAY_BEHAVIOUR"]
        if behaviour == "good":
            delay = int(rng.normal(-2, 4))
        elif behaviour == "average":
            delay = int(rng.normal(8, 8))
        else:
            delay = int(rng.normal(30, 18))
        pay_date = due_date + pd.Timedelta(days=delay)
        # A few invoices are simply never paid (bad debt candidates)
        unpaid = (behaviour == "poor" and rng.random() < 0.04) or rng.random() < 0.003
        if unpaid or pay_date > AS_OF:
            pay.append(
                {
                    "BELNR": f"1{vbrk_id}",
                    "VBELN": vbrk_id,
                    "KUNNR": cust["KUNNR"],
                    "AUGDT": pd.NaT,  # clearing date (null = still open -> BSID)
                    "WRBTR": inv_value,
                    "STATUS": "Open",
                }
            )
        else:
            pay.append(
                {
                    "BELNR": f"1{vbrk_id}",
                    "VBELN": vbrk_id,
                    "KUNNR": cust["KUNNR"],
                    "AUGDT": pay_date,
                    "WRBTR": inv_value,
                    "STATUS": "Cleared",
                }
            )

    return (
        pd.DataFrame(vbak),
        pd.DataFrame(vbap),
        pd.DataFrame(likp),
        pd.DataFrame(lips),
        pd.DataFrame(vbrk),
        pd.DataFrame(vbrp),
        pd.DataFrame(pay),
    )


def main():
    cfg.RAW_DIR.mkdir(parents=True, exist_ok=True)
    customers = make_customers()
    materials = make_materials()
    vbak, vbap, likp, lips, vbrk, vbrp, pay = build_orders(customers, materials)

    tables = {
        "KNA1": customers,
        "MARA": materials,
        "VBAK": vbak,
        "VBAP": vbap,
        "LIKP": likp,
        "LIPS": lips,
        "VBRK": vbrk,
        "VBRP": vbrp,
        "BSEG_PAY": pay,
    }
    for name, df in tables.items():
        path = cfg.RAW_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"{name:<9} {len(df):>7,} rows -> {path.relative_to(cfg.ROOT)}")


if __name__ == "__main__":
    main()
