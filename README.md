# FOCUS SQL Lab

A web page for practising SQL on FOCUS sample data and the FOCUS specification's worked examples. DuckDB-WASM runs the queries in the browser, so the
server only serves static files: no database, no login, no API.

## What's in it

| Table | Rows | Source |
| --- | --- | --- |
| `cau_sample` | 100,000 | FinOps Foundation [FOCUS-Sample-Data](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data), anonymised FOCUS 1.0 data, given FOCUS 1.5 column names |
| `cau_examples` | 493 | FOCUS 1.5 worked-example Cost and Usage rows from the [specification](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec) |
| `SkuPrice`, `InvoiceDetail`, `ContractCommitment`, `CorrectionExamples` | small | Specification worked examples |

`CostAndUsage` is a view that points at either `cau_sample` or `cau_examples`, chosen on the page.

The example menu holds 11 practice queries for the sample data and the specification's 66 example queries, converted from BigQuery SQL to DuckDB SQL. 74 of the 77 run. The three that don't are labelled on the page with the reason.

## Rebuild the data

Needs Python with `duckdb` and `sqlglot`, a clone of `FOCUS_Spec` (branch `working_draft`), and
`focus_sample_100000.csv.gz` from FOCUS-Sample-Data.

```bash
python -I tools/build_data.py <FOCUS_Spec clone> <dir with focus_sample_100000.csv.gz> site/data
python -I tools/extract_sql.py <FOCUS_Spec clone> site/data site/examples.json
```

## Run locally

```bash
python3 -m http.server 8644 --directory site
```

## Deploy

Coolify: add the repository as a resource with the Dockerfile build pack, port 80.

## Licence and credits

The data and the example queries come from the FOCUS project and are used under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Changes: data cleaned and typed, and queries converted to DuckDB SQL. Not affiliated with the FinOps Foundation.
