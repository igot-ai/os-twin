---
name: question-library
description: Use this skill to maintain and query a reusable library of proven risk questions organized by Risk Theme × Data Domain × Analytical Lens.
tags: [audit, risk-officer, question-library, playbook, continuous-audit]
: core
---

# question-library

## Overview

Over time, the Risk Officer builds a reusable library of proven questions — organized by risk theme, data domain, and analytical lens. This library is the organization's institutional knowledge for continuous audit. Other audit skills reference this library as a starting point when formulating new analytical requests.

## When to Use

- As a reference when the `analytical-lenses` skill needs question templates
- When starting an investigation in a familiar domain — check the library first
- When a novel risk pattern is discovered — add the effective question to the library
- During quarterly self-assessment to evaluate question coverage gaps

## Artifacts Produced

| Artifact | Format | Location |
|----------|--------|----------|
| Question library | Markdown | `<war-room>/artifacts/question-library.md` or persistent at `skills/roles/audit/question-library/library.md` |

## Instructions

### 1. Understand the Three Dimensions

Questions are organized in a 3D grid:

**Dimension 1 — Risk Theme (rows):**
Fraud, Revenue Leakage, Governance, Operational Efficiency, Data Integrity, Regulatory Compliance

**Dimension 2 — Data Domain (columns):**
Vendor Payments, Lease Revenue, Capital Projects, Payroll, Asset Management, Compliance Filings

**Dimension 3 — Analytical Lens (layers):**
Distribution, Deviation, Relationship, Temporality, Compounding

### 2. Query the Library

When formulating questions, look up the intersection of your investigation's three dimensions:

```
Theme: [from scope-request → Theme]
Domain: [from scope-request → Domain]
Lens:   [from analytical-lenses → selected lens]
```

### 3. Starter Library — 20 Proven Questions

#### Fraud × Vendor Payments

| Lens | Question |
|------|----------|
| Distribution | What is the frequency distribution of payment amounts by approver, and does any approver show unnatural clustering near their authorization threshold? |
| Relationship | Which approver-vendor pairs have exclusive relationships (one approver accounts for 100% of a vendor's payments), and what is the total financial value of each exclusive pair? |
| Temporality | What percentage of payments are processed on weekends or holidays? For those, do they share secondary characteristics (same approver, same method, higher amounts)? |
| Compounding | Which vendors trigger 3+ anomaly flags simultaneously (inactive status, missing PO, weekend processing, budget overrun, duplicate invoice)? Produce a compound risk profile. |

#### Fraud × Lease Revenue

| Lens | Question |
|------|----------|
| Relationship | Do any tenant names match or partially match any names in the vendor payment dataset (vendor names, approver names)? For each match, what is the financial exposure on both sides? |

#### Revenue Leakage × Lease Revenue

| Lens | Question |
|------|----------|
| Deviation | What is the market alignment ratio for every active lease, and what is the total annualized revenue gap for all leases below 75% of market rate? |
| Temporality | Which leases have missed their contractual rent escalation dates? What is the cumulative revenue impact from the missed date to today? |
| Compounding | Which leases simultaneously exhibit below-market rent, no escalation clause, minimal deposit, and extended terms? (Sweetheart deal indicators) |

#### Governance × Vendor Payments

| Lens | Question |
|------|----------|
| Deviation | Which payments were processed without a corresponding purchase order? What was the approval authority level, and does it comply with the delegation-of-authority matrix? |
| Relationship | Does any single individual appear as both the requestor and the approver, or as both the approver and the payment executor? (Segregation of duties) |

#### Governance × Lease Revenue

| Lens | Question |
|------|----------|
| Deviation | Which leases required approval authority above standard level? How do their terms compare to portfolio averages in rent/sqft, deposit, escalation, and duration? |
| Relationship | For every related-party lease, compare all terms against the portfolio median for the same property type. Quantify total deviation across rent, deposit, escalation, and term. |

#### Data Integrity × Vendor Payments

| Lens | Question |
|------|----------|
| Distribution | Are there any invoice numbers that appear more than once? For duplicates, are amounts, dates, and vendors identical or different? |

#### Data Integrity × Lease Revenue

| Lens | Question |
|------|----------|
| Deviation | Any mismatches between occupancy_status and billing_status? Vacant but Active billing, or Occupied but Inactive billing? |
| Temporality | For leases with zero rent collected this period, when was the last successful collection? Is the gap a timing delay (<15 days) or genuine delinquency (>30 days)? |

#### Operational × Vendor Payments

| Lens | Question |
|------|----------|
| Temporality | What is the average days_invoice_to_payment? Which transactions have processing times >2× the average? Correlation with other anomaly indicators? |
| Deviation | Which vendors have cumulative YTD spend exceeding 80% of budget in Q1? At current run rates, which will exceed annual budget, and by how much? |

#### Compliance × Lease Revenue

| Lens | Question |
|------|----------|
| Deviation | For all leases with escalation clauses, calculate expected rent after each cycle. Compare against current monthly_rent_usd. Flag any lease where current rent is lower than expected. |
| Compounding | Apply all lease detection rules to every lease. Produce: rule pass/fail by lease, aggregate pass rate by rule, and leases failing 2+ rules ranked by financial exposure. |

#### Cross-Domain × Both Datasets

| Lens | Question |
|------|----------|
| Compounding | Produce a unified property-level risk scorecard: aggregate all expenditure-side and revenue-side anomalies per property. Which properties are hot spots across both domains? |

### 4. Expand the Library

When a new investigation produces an effective question:

1. Classify it: `[Theme] × [Domain] × [Lens]`
2. Generalize the question — replace specific entity names with placeholders
3. Add it to the appropriate cell in the library
4. Note the source investigation for traceability

### 5. Handoff to Data Analyst

Questions from this library are **not sent directly** to the data analyst. They serve as templates for the `analytical-lenses` skill, which fills in the specific parameters, and the `structure-data-request` skill, which wraps them in the formal DATA template.

**Pipeline:** `question-library` → `analytical-lenses` (fill placeholders) → `structure-data-request` (DATA template) → data analyst `task` message.

### 6. Quarterly Self-Assessment

Use this checklist to evaluate question coverage:

- [ ] All five analytical lenses are used regularly, not just one or two
- [ ] Questions specify benchmarks or baselines for comparison
- [ ] Questions define expected output format
- [ ] No vague questions — all have specific detection logic
- [ ] Library is updated when novel risk patterns are discovered
- [ ] Effective questions are shared with the broader risk team

## Verification

After updating the library:
1. New questions are classified across all three dimensions
2. Questions are generalized (no entity-specific names in templates)
3. Source investigation is documented for traceability
4. No duplicate questions exist in the same cell
