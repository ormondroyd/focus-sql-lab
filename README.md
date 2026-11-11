# FOCUS SQL Lab

A web page for practising SQL on FOCUS sample data and exploring the FOCUS data model. DuckDB-WASM runs the
queries in the browser, so the server only serves static files: no database, no login, no API.

## What it does

- **Query:** run the specification's 66 example queries exactly as published, or the lab's 11 practice queries.
  62 of the 66 run in DuckDB as published; the page explains why the other 4 don't.
- **Response explorer:** pivot and chart any query result by any column, using Perspective (FINOS).
- **Data model:** the five FOCUS 1.5 datasets with lines between the key columns of every documented join. Click a
  join to see the spec's wording, the lab's join SQL and how well the keys match in the chosen data source. Click a
  column to see its definition and a profile of its values.
- **Data sources:** switch between the accepted 1.0 sample, two samples proposed in open FOCUS-Sample-Data pull
  requests (1.3 and 1.4), and the specification's 1.5 worked examples. The Data model shows which joins work in each.

## How the spec's queries run unchanged

The specification writes its queries in ANSI SQL, using BigQuery's JSON functions where it reads JSON, and marks each
value the reader supplies with `?`.

- **Inputs:** the page shows one input for each `?`, with a type (text, number or timestamp) and a value the lab
  suggests from the data. When the query runs, each value takes the place of its `?` as a typed SQL literal, the way a
  database client binds a parameter. The query text itself is never changed.
- **BigQuery names:** [site/lab-setup.sql](site/lab-setup.sql) runs before any query. It gives DuckDB BigQuery's
  `JSON_VALUE`, `JSON_EXTRACT_ARRAY`, `JSON_VALUE_ARRAY` and `FLOAT64`, with BigQuery's behaviour, and defines the
  `focus_data` table name that the version migration guide uses without defining. The page shows this file.
- **The 4 that don't run:** one uses BigQuery's `value IN UNNEST(array)` form, one has a `GROUP BY` name that
  DuckDB resolves to a table column rather than the SELECT alias, one uses `JSON_TABLE`, and one uses a stand-in
  column name (`x_CustomColumn`).

## What the lab made

Everything the lab made is labelled on the page:

- **Names:** every table name (`cau_sample`, `cau_pr7`, `cc_examples` and so on), and the view `focus_data`.
  `CostAndUsage`, `SkuPrice`, `InvoiceDetail`, `ContractCommitment` and `BillingPeriod` are FOCUS dataset names: on
  the page they are views onto the chosen data source's tables.
- **Columns:** `x_SampleRowId`, `x_Dataset` and `x_ExampleFile`. In `cau_sample`, `ServiceProviderName` and
  `HostProviderName`, derived using the spec's migration guidance, and the FOCUS 1.5 columns that 1.0 lacks, added
  empty. The sample is FOCUS 1.0 data, not 1.5 data. The proposed 1.3 and 1.4 samples also have the 1.5 columns they
  lack added empty.
- **Queries:** the 11 practice queries, written in DuckDB SQL.
- **Data model:** the relationship names, key pairs and join SQL. The specification describes relationships only in
  prose, which the page quotes.

## Repository layout

Everything under `site/focus/` is derived from FOCUS project material (CC BY 4.0). Everything else is original to
this project. [NOTICE.md](NOTICE.md) lists each derived file's source, upstream version and changes.

```
README.md, NOTICE.md
Dockerfile, nginx.conf        serve site/ with nginx
tools/                        build scripts, plus practice.json (the practice queries)
site/
  index.html                  the page
  lab-setup.sql               what the lab adds to DuckDB so the spec's queries run as published
  practice-queries.json       the practice queries, with test results (built from tools/practice.json)
  focus/                      FOCUS-derived, rebuilt by the tools; not edited by hand
    data/*.parquet            sample data and the specification's worked examples
    data/manifest.json        table list, row counts, column types and the columns the lab added
    spec-queries.json         the specification's example queries, verbatim, with suggested inputs and test results
    model.json                datasets, columns and relationships from the specification
```

## Data sources

The page has one data source switch. It points all five FOCUS dataset names at that source's tables. A dataset the
source doesn't have points at an empty table with the specification's columns, so queries and joins still run.

| Source | Status | Cost and Usage | Contract Commitment | Invoice Detail | Billing Period | SKU Price |
| --- | --- | --- | --- | --- | --- | --- |
| FOCUS-Sample-Data 1.0 | accepted | `cau_sample`, 100,000 | – | – | – | – |
| FOCUS 1.3, [Sample-Data PR #7](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/pull/7) | proposed, not accepted | `cau_pr7`, 3,000 | `cc_pr7`, 66 | – | – | – |
| FOCUS 1.4, [Sample-Data PR #5](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/pull/5) | draft, not accepted | `cau_pr5`, 1,000 | `cc_pr5`, 1,000 | `inv_pr5`, 1,000 | `bp_pr5`, 1,000 | – |
| Spec 1.5 worked examples | in the specification | `cau_examples`, 493 | `cc_examples`, 9 | `inv_examples`, 8 | – | `sku_examples`, 62 |

`CorrectionExamples` (114 rows, the specification's correction-handling examples) sits outside the switch.

Decimal columns are stored as 64-bit floating point (DOUBLE), one of the precisions the spec's NumericFormat attribute
allows. Sums of charges and credits can therefore leave tiny remainders instead of exactly zero.

## Rebuild

You need Python with `duckdb==1.5.4` (see `tools/requirements.txt`), a clone of `FOCUS_Spec` (branch
`working_draft`), and a raw data folder holding `focus_sample_100000.csv.gz` from FOCUS-Sample-Data, plus `pr7-1.3/`
and `pr5-1.4/` with the CSV files from each pull request's `FOCUS-1.3/` and `FOCUS-1.4/` folder at the commits listed
in [NOTICE.md](NOTICE.md).

```bash
python -I tools/build_data.py <FOCUS_Spec clone> <raw data folder> site/focus/data
python -I tools/extract_sql.py <FOCUS_Spec clone> site
python -I tools/extract_model.py <FOCUS_Spec clone> site
```

## Run locally

```bash
python3 -m http.server 8644 --directory site
```

## Deploy

On Coolify, add this repository as a Public Repository resource using the Dockerfile build pack and port 80.
A GitHub webhook redeploys it on every push to `main`.
