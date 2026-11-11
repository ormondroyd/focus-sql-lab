# FOCUS SQL Lab

A web page for practising SQL on FOCUS sample data and exploring the FOCUS data model. DuckDB-WASM runs the
queries in the browser, so the server only serves static files: no database, no login, no API.

## What it does

- **Query:** run the specification's 66 example queries exactly as published, or the lab's 11 practice queries.
  62 of the 66 run in DuckDB as published; the page explains why the other 4 don't.
- **Response explorer:** pivot and chart any query result by any column, using Perspective (FINOS).
- **Data model:** the five FOCUS 1.5 datasets with lines between the key columns of every documented join. Click a
  join to see the spec's wording, the lab's join SQL and how well the keys match in the loaded data. Click a column to
  see its definition and a profile of its values.

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

- **Names:** the tables `cau_sample`, `cau_examples` and `CorrectionExamples`, and the view `focus_data`.
  `CostAndUsage`, `SkuPrice`, `InvoiceDetail`, `ContractCommitment` and `BillingPeriod` are FOCUS dataset names.
- **Columns:** `x_SampleRowId`, `x_Dataset` and `x_ExampleFile`. In `cau_sample`, `ServiceProviderName` and
  `HostProviderName`, derived using the spec's migration guidance, and the FOCUS 1.5 columns that 1.0 lacks, added
  empty. The sample is FOCUS 1.0 data, not 1.5 data.
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

## Tables

| Table | Rows | Source |
| --- | --- | --- |
| `cau_sample` | 100,000 | FOCUS-Sample-Data: anonymised FOCUS 1.0 data, with FOCUS 1.5 columns added by the lab |
| `cau_examples` | 493 | The specification's worked-example Cost and Usage rows |
| `SkuPrice`, `InvoiceDetail`, `ContractCommitment`, `CorrectionExamples` | small | The specification's worked examples |
| `BillingPeriod` | 0 | Created empty from the specification's columns, because the spec has no example data for it |

`CostAndUsage` is a view that points at either `cau_sample` or `cau_examples`, chosen on the page.

Decimal columns are stored as 64-bit floating point (DOUBLE), one of the precisions the spec's NumericFormat attribute
allows. Sums of charges and credits can therefore leave tiny remainders instead of exactly zero.

## Rebuild

You need Python with `duckdb`, a clone of `FOCUS_Spec` (branch `working_draft`), and
`focus_sample_100000.csv.gz` from FOCUS-Sample-Data.

```bash
python -I tools/build_data.py <FOCUS_Spec clone> <folder with focus_sample_100000.csv.gz> site/focus/data
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
