# FOCUS SQL Lab

A web page for practising SQL on FOCUS sample data and exploring the FOCUS data model. DuckDB-WASM runs the
queries in the browser, so the server only serves static files: no database, no login, no API.

## What it does

- **Query:** run SQL against the data, choosing from 11 practice queries and the specification's 66 example
  queries. 74 of the 77 run; the three that don't explain why on the page.
- **Response explorer:** pivot and chart any query result by any column, using Perspective (FINOS).
- **Data model:** the five FOCUS 1.5 datasets with lines between the key columns of every documented join. Click a
  join to see the spec's wording, the join SQL and how well the keys match in the loaded data. Click a column to
  see its definition and a profile of its values.

## Repository layout

Everything under `site/focus/` is derived from FOCUS project material (CC BY 4.0). Everything else is original to
this project. [NOTICE.md](NOTICE.md) lists each derived file's source, upstream version and changes.

```
README.md, NOTICE.md
Dockerfile, nginx.conf        serve site/ with nginx
tools/                        build scripts, plus practice.json (the practice queries)
site/
  index.html                  the page
  practice-queries.json       the practice queries, with test results (built from tools/practice.json)
  focus/                      FOCUS-derived, rebuilt by the tools; not edited by hand
    data/*.parquet            sample data and the specification's worked examples
    data/manifest.json        table list, row counts and column types
    spec-queries.json         the specification's example queries, converted to DuckDB SQL
    model.json                datasets, columns and relationships from the specification
```

## Tables

| Table | Rows | Source |
| --- | --- | --- |
| `cau_sample` | 100,000 | FOCUS-Sample-Data: anonymised FOCUS 1.0 data, given FOCUS 1.5 column names |
| `cau_examples` | 493 | The specification's worked-example Cost and Usage rows |
| `SkuPrice`, `InvoiceDetail`, `ContractCommitment`, `CorrectionExamples` | small | The specification's worked examples |
| `BillingPeriod` | 0 | Created empty from the specification's columns, because the spec has no example data for it |

`CostAndUsage` is a view that points at either `cau_sample` or `cau_examples`, chosen on the page.

## Rebuild

You need Python with `duckdb` and `sqlglot`, a clone of `FOCUS_Spec` (branch `working_draft`), and
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
