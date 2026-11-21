-- =====================================================================
-- O2C KPI queries (SQLite dialect). Replace :as_of with a date string.
-- =====================================================================

-- name: dso
-- DSO = Open receivables / credit sales in last 90 days * 90
SELECT ROUND(
    (SELECT COALESCE(SUM(inv.NETWR), 0)
       FROM VBRK inv JOIN BSEG_PAY p ON p.VBELN = inv.VBELN
      WHERE p.STATUS = 'Open'
         OR p.AUGDT > :as_of)
    /
    (SELECT SUM(NETWR) FROM VBRK
      WHERE FKDAT > DATE(:as_of, '-90 day') AND FKDAT <= :as_of)
    * 90, 1) AS dso_days;

-- name: otif
SELECT
    ROUND(100.0 * AVG(on_time), 1)                  AS on_time_pct,
    ROUND(100.0 * AVG(in_full), 1)                  AS in_full_pct,
    ROUND(100.0 * AVG(on_time * in_full), 1)        AS otif_pct
FROM v_otif;

-- name: otif_by_month
SELECT STRFTIME('%Y-%m', order_date) AS month,
       ROUND(100.0 * AVG(on_time * in_full), 1) AS otif_pct,
       COUNT(*) AS orders
FROM v_otif
GROUP BY 1 ORDER BY 1;

-- name: cycle_time
-- Average days in each stage of the order-to-cash cycle
SELECT
    ROUND(AVG(JULIANDAY(goods_issue_date) - JULIANDAY(order_date)), 1)    AS order_to_delivery_days,
    ROUND(AVG(JULIANDAY(invoice_date) - JULIANDAY(goods_issue_date)), 1)  AS delivery_to_invoice_days,
    ROUND(AVG(JULIANDAY(payment_date) - JULIANDAY(invoice_date)), 1)      AS invoice_to_cash_days,
    ROUND(AVG(JULIANDAY(payment_date) - JULIANDAY(order_date)), 1)        AS total_o2c_days
FROM v_order_lifecycle
WHERE payment_date IS NOT NULL;

-- name: ageing
-- Receivables ageing buckets (open invoices only)
SELECT
    CASE
        WHEN JULIANDAY(:as_of) - JULIANDAY(inv.ZFBDT) <= 0  THEN '0. Not due'
        WHEN JULIANDAY(:as_of) - JULIANDAY(inv.ZFBDT) <= 30 THEN '1. 1-30 days'
        WHEN JULIANDAY(:as_of) - JULIANDAY(inv.ZFBDT) <= 60 THEN '2. 31-60 days'
        WHEN JULIANDAY(:as_of) - JULIANDAY(inv.ZFBDT) <= 90 THEN '3. 61-90 days'
        ELSE '4. 90+ days'
    END AS bucket,
    COUNT(*)                        AS invoices,
    ROUND(SUM(inv.NETWR), 0)        AS open_amount
FROM VBRK inv
JOIN BSEG_PAY p ON p.VBELN = inv.VBELN
WHERE p.STATUS = 'Open'
GROUP BY bucket
ORDER BY bucket;

-- name: top_overdue_customers
SELECT c.KUNNR AS customer_id, c.NAME1 AS customer_name, c.KEY_ACCOUNT AS key_account,
       COUNT(*) AS overdue_invoices,
       ROUND(SUM(inv.NETWR), 0) AS overdue_amount,
       ROUND(MAX(JULIANDAY(:as_of) - JULIANDAY(inv.ZFBDT)), 0) AS max_days_overdue
FROM VBRK inv
JOIN BSEG_PAY p ON p.VBELN = inv.VBELN
JOIN KNA1 c ON c.KUNNR = inv.KUNNR
WHERE p.STATUS = 'Open' AND inv.ZFBDT < :as_of
GROUP BY c.KUNNR, c.NAME1, c.KEY_ACCOUNT
ORDER BY overdue_amount DESC
LIMIT 15;

-- name: monthly_revenue_vs_collections
SELECT m.month,
       ROUND(COALESCE(r.revenue, 0), 0)     AS revenue,
       ROUND(COALESCE(c.collections, 0), 0) AS collections
FROM (SELECT DISTINCT STRFTIME('%Y-%m', FKDAT) AS month FROM VBRK) m
LEFT JOIN (SELECT STRFTIME('%Y-%m', FKDAT) AS month, SUM(NETWR) AS revenue
             FROM VBRK GROUP BY 1) r ON r.month = m.month
LEFT JOIN (SELECT STRFTIME('%Y-%m', AUGDT) AS month, SUM(WRBTR) AS collections
             FROM BSEG_PAY WHERE AUGDT IS NOT NULL GROUP BY 1) c ON c.month = m.month
ORDER BY m.month;

-- name: customer_pareto
-- ABC classification: A = top 80% of revenue, B = next 15%, C = last 5%
WITH rev AS (
    SELECT c.KUNNR AS customer_id, c.NAME1 AS customer_name, SUM(i.NETWR) AS revenue
    FROM VBRK i JOIN KNA1 c ON c.KUNNR = i.KUNNR
    GROUP BY c.KUNNR, c.NAME1
),
ranked AS (
    SELECT *, SUM(revenue) OVER (ORDER BY revenue DESC) * 1.0 / SUM(revenue) OVER () AS cum_share
    FROM rev
)
SELECT customer_id, customer_name, ROUND(revenue, 0) AS revenue,
       ROUND(100 * cum_share, 1) AS cum_share_pct,
       CASE WHEN cum_share <= 0.80 THEN 'A' WHEN cum_share <= 0.95 THEN 'B' ELSE 'C' END AS abc_class
FROM ranked ORDER BY revenue DESC;

-- name: category_margin
SELECT m.MATKL AS category,
       ROUND(SUM(p.NETWR), 0) AS revenue,
       ROUND(SUM(p.NETWR - p.COST), 0) AS gross_margin,
       ROUND(100.0 * SUM(p.NETWR - p.COST) / SUM(p.NETWR), 1) AS margin_pct
FROM VBRP p JOIN MARA m ON m.MATNR = p.MATNR
GROUP BY m.MATKL ORDER BY revenue DESC;

-- name: accessory_attach_rate
-- Share of orders containing at least one accessory (cross-sell opportunity)
SELECT ROUND(100.0 * SUM(has_acc) / COUNT(*), 1) AS orders_with_accessory_pct
FROM (
    SELECT a.VBELN,
           MAX(CASE WHEN m.MTART = 'Accessory' THEN 1 ELSE 0 END) AS has_acc
    FROM VBAP a JOIN MARA m ON m.MATNR = a.MATNR
    GROUP BY a.VBELN
);

-- name: blocked_orders
SELECT sales_order, customer_name, order_date, order_value,
       ROUND(JULIANDAY(:as_of) - JULIANDAY(order_date), 0) AS days_open
FROM v_order_lifecycle
WHERE delivery_block <> '' AND goods_issue_date IS NULL
ORDER BY order_value DESC;

-- name: discount_leakage
-- Discount value given away by customer type
SELECT c.KTOKD AS customer_type,
       ROUND(SUM(a.KWMENG * a.NETPR * a.DISCOUNT), 0) AS discount_given,
       ROUND(100.0 * SUM(a.KWMENG * a.NETPR * a.DISCOUNT) / SUM(a.KWMENG * a.NETPR), 2) AS discount_pct
FROM VBAP a
JOIN VBAK so ON so.VBELN = a.VBELN
JOIN KNA1 c ON c.KUNNR = so.KUNNR
GROUP BY c.KTOKD ORDER BY discount_given DESC;

-- name: declining_accounts
-- Customers whose last-90-day revenue fell vs the prior 90 days
WITH r AS (
    SELECT KUNNR,
           SUM(CASE WHEN FKDAT > DATE(:as_of,'-90 day') THEN NETWR ELSE 0 END) AS last_90,
           SUM(CASE WHEN FKDAT <= DATE(:as_of,'-90 day') AND FKDAT > DATE(:as_of,'-180 day') THEN NETWR ELSE 0 END) AS prev_90
    FROM VBRK GROUP BY KUNNR
)
SELECT c.KUNNR AS customer_id, c.NAME1 AS customer_name, c.KEY_ACCOUNT AS key_account,
       ROUND(prev_90, 0) AS prev_90_revenue, ROUND(last_90, 0) AS last_90_revenue,
       ROUND(100.0 * (last_90 - prev_90) / prev_90, 1) AS change_pct
FROM r JOIN KNA1 c ON c.KUNNR = r.KUNNR
WHERE prev_90 > 0 AND last_90 < prev_90
ORDER BY change_pct ASC LIMIT 15;
