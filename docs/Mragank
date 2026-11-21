# Business Requirements Document (BRD)

**Project:** Order-to-Cash Visibility & Automation
**Client (fictional):** B2B distributor of auto spare parts & accessories (dealers, workshops, fleets)
**Author:** _your name_ · **Version:** 1.0

## 1. Background & problem statement
Order, delivery, invoice and payment data sit in separate SAP modules (SD, LE, FI). Teams build manual
Excel reports each week, so overdue payments and delayed orders are found late, and key accounts are
chased inconsistently.

## 2. Objectives
1. Give one view of every order from sales order to cash.
2. Raise OTIF to ≥ 95% and cut DSO to ≤ 45 days.
3. Replace manual weekly reporting with automation.
4. Identify revenue and margin opportunities (cross-sell, discounts, at-risk accounts).

## 3. Scope
**In scope:** key B2B accounts, parts & accessories orders, delivery, billing, receivables, KPI dashboard, automation.
**Out of scope:** procurement, production, B2C/e-commerce, tax and GST filing.

## 4. Stakeholders
| Stakeholder | Interest | Needs |
|---|---|---|
| Sales / key account managers | Customer relationships, growth | Order status, overdue by account, cross-sell leads |
| Logistics & warehouse | On-time, in-full delivery | Blocked orders, OTIF drivers |
| Finance / collections | Cash flow | Ageing, DSO, risk scoring, reminders |
| Credit control | Risk | Late-payment prediction, credit exposure |
| IT / SAP team | Data & access | Clear table list, refresh schedule |
| Management | Performance | KPI dashboard vs targets |

## 5. Functional requirements (user stories)
| ID | As a… | I want… | So that… | Priority |
|---|---|---|---|---|
| FR1 | Key account manager | to see every order's status from order to payment | I can answer customers quickly | Must |
| FR2 | Collections executive | an ageing report and overdue list by customer | I can prioritise follow-ups | Must |
| FR3 | Collections executive | auto-generated payment reminder drafts | I save manual effort | Should |
| FR4 | Logistics head | a list of blocked and late orders | I can release them fast | Must |
| FR5 | Sales head | accessory attach rate and declining accounts | I can plan growth actions | Should |
| FR6 | Credit controller | a late-payment risk score per open invoice | I can act before payment is late | Should |
| FR7 | Finance manager | revenue vs collections and a DSO what-if | I can plan working capital | Should |
| FR8 | Manager | a weekly report delivered automatically | I don't depend on manual Excel | Must |

## 6. Non-functional requirements
Refresh at least weekly · reproducible results · data-quality checks on load · read-only database access for the Q&A feature.

## 7. Process: As-Is vs To-Be
```
AS-IS:  SAP extracts -> manual Excel merge -> weekly email -> reactive follow-up (days of delay)

TO-BE:  SAP tables -> automated ETL + quality checks -> KPI engine -> dashboard
                                                      -> weekly report + reminders
                                                      -> risk scores / anomaly flags
```

## 8. Success metrics
| Metric | Baseline | Target |
|---|---|---|
| OTIF % | 74.7 | ≥ 95 |
| DSO | 48.8 days | ≤ 45 days |
| Manual reporting time | ~4 hrs/week (assumed) | < 15 min |
| Overdue 90+ days | 35% of overdue | < 10% |

## 9. Roadmap
| Phase | Deliverable |
|---|---|
| 1 | Data model, ETL, KPI SQL |
| 2 | Dashboard and weekly automation |
| 3 | ML: late-payment risk, anomalies, forecast |
| 4 | Natural-language data assistant, rollout and training |

## 10. Risks & assumptions
- Real SAP data quality may differ (duplicates, missing dates). Mitigation: automated data-quality checks.
- Users may not trust ML scores at first. Mitigation: show the drivers and track accuracy.
- Assumption: payment terms are held at customer level (field ZTERM).
