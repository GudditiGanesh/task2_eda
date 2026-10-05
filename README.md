# Task 2 – Exploratory Data Analysis & Business Intelligence (ApexPlanet)

## Run
1. Put `ApexPlanet_DataAnalytics_Dataset.xlsx` in this folder (next to `main.py`).
2. `pip install -r requirements.txt`
3. `python main.py`   (or `python main.py path\to\file.xlsx`)

If the dataset is missing, a synthetic sample is used so you can test the pipeline.

## What it does
| Step | Output |
|---|---|
| Load, validate, clean (duplicates, missing values, dates) | `cleaned_data.csv/.xlsx`, cleaning log |
| Descriptive stats (mean, median via quartiles, mode, std) | console + report |
| Univariate charts (histograms, box plots, count plots) | `charts/` |
| Multivariate (heatmap, scatter plots, pair plot) | `charts/` |
| Outlier detection (IQR) | console + report |
| SQL business analysis (SQLite, GROUP BY, JOIN, etc.) | `sql_queries.sql`, `sql_results/*.csv`, `business.db` |
| Auto-written insights & recommendations | console + report |
| Static dashboard mock-up (KPI cards + 4 charts) | `dashboard_mockup.png` |
| Full EDA report | `eda_report.html` |

Columns are auto-detected by name (date, sales/revenue, profit, quantity, category, product, customer, region).
If a role is not found, the related SQL query/chart is skipped. Check the "Detected columns" line in the
cleaning log, and edit the keyword lists in `detect()` in `main.py` if your headers are unusual.

## Suggested GitHub structure
```
task2_eda/
├── main.py
├── requirements.txt
├── README.md
├── ApexPlanet_DataAnalytics_Dataset.xlsx
└── output/
```
