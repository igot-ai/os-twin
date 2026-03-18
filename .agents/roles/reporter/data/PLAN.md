# Sales Performance Report Generation

## Config
- **Epic**: EPIC-SALES-REPORT
- **Owner**: Engineer Manager
- **Roles**: `reporter`, `engineer`
- **Data Source**: `data/sales-performance.csv`
- **Output**: `sales-performance-report.pdf`

## Goal

Build an automated pipeline where the **engineer** parses `sales-performance.csv` into a report spec JSON, and the **reporter** generates a polished PDF from that spec — demonstrating the dynamic report engine in action.

# Epics

### EPIC-1 — Data Ingestion (Engineer)
Build a Python script `data/build_sales_spec.py` that:
1. Reads `sales-performance.csv`
2. Aggregates metrics (total revenue, units, close rate, Q-over-Q trends)
3. Groups data by region and product for tables and charts
4. Outputs a fully-formed report spec JSON: `data/sales-report-spec.json`

**Acceptance Criteria:**
- Script reads CSV without hardcoded paths (accepts `--csv` and `--output` args)
- Spec includes: cover, TOC, metrics page, data tables, bar charts, pie chart, timeline
- All numbers computed from CSV, zero manual data entry

---

## EPIC-2 — Report Spec Template (Reporter)
Define the spec structure for the sales performance report using the engine's 13 components:

| Page | Component | Data From CSV |
|------|-----------|---------------|
| 1 | `cover` | Report title + quarter range |
| 2 | `toc` | Auto from pages |
| 3 | `metrics` | Total revenue, units, avg deal size, close rate, customer counts |
| 4 | `data_table` | Revenue by region × product |
| 5 | `bar_chart` | Revenue by region |
| 6 | `bar_chart` | Revenue by product |
| 7 | `pie_chart` | Revenue share by region |
| 8 | `data_table` | Top sales reps by revenue |
| 9 | `bar_chart` | Target attainment % by rep |
| 10 | `timeline` | Quarterly milestones |

**Acceptance Criteria:**
- All 10 pages render without errors
- Charts labeled with proper data
- Consistent brand styling via `brand.json`

---

## EPIC-3 — End-to-End Pipeline (Engineer + Reporter)
Wire it together:
```bash
# 1. Engineer generates the spec from CSV
python data/build_sales_spec.py --csv data/sales-performance.csv --output data/sales-report-spec.json

# 2. Reporter generates the PDF from spec
python -m reporter generate data/sales-report-spec.json -o sales-performance-report.pdf
```

**Acceptance Criteria:**
- Single `make report` or shell script runs both steps
- PDF is ≥ 10 pages, all data sourced from CSV
- Modifying CSV data → regenerate → different report (no code changes)

---

## Definition of Done

- [ ] `build_sales_spec.py` parses CSV → JSON spec (zero hardcoded values)
- [ ] Report spec uses ≥ 6 different component types
- [ ] PDF renders all pages without errors
- [ ] Pipeline is reproducible: change CSV → get new report
- [ ] QA reviewed in `QA.md`

## Tasks

| ID | Epic | Task | Role | Status |
|----|------|------|------|--------|
| TASK-001 | EPIC-1 | Create `build_sales_spec.py` with CSV parsing + aggregation | engineer | `[ ]` |
| TASK-002 | EPIC-1 | Add CLI args (`--csv`, `--output`, `--brand`) | engineer | `[ ]` |
| TASK-003 | EPIC-2 | Design report spec template with 10 pages | reporter | `[ ]` |
| TASK-004 | EPIC-2 | Test spec renders via `python -m reporter validate` | reporter | `[ ]` |
| TASK-005 | EPIC-3 | Create `generate-report.sh` pipeline script | engineer | `[ ]` |
| TASK-006 | EPIC-3 | End-to-end test: CSV → spec → PDF | engineer | `[ ]` |
| TASK-007 | — | QA review of generated PDF | qa | `[ ]` |

## Release Notes

_Pending — updated by engineer after implementation._
