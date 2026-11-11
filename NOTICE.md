# Notice

FOCUS SQL Lab is an independent project. It is not affiliated with or endorsed by the FinOps Foundation, the
FOCUS project, the Joint Development Foundation or the Linux Foundation.

## What is original to this project

Everything outside `site/focus/`:

- `site/index.html`: the page (query editor, response explorer, data model view)
- `tools/practice.json`: the practice queries, which are built into `site/practice-queries.json`
- `tools/*.py`: the build scripts
- `Dockerfile`, `nginx.conf`, `README.md`, `NOTICE.md`

No licence has been chosen yet for this original material.

## Material derived from FOCUS: `site/focus/`

Everything in `site/focus/` is derived from FOCUS project material. It is used under the
[Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/).

> Copyright (c) Joint Development Foundation Projects, LLC, FinOps Open Cost and Usage Specification (FOCUS)
> Series and its contributors.

| File | Derived from | Upstream version | Changes made here |
| --- | --- | --- | --- |
| `focus/data/cau_sample.parquet` | [FOCUS-Sample-Data](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data), `FOCUS-1.0/focus_sample_100000.csv.gz` | `main` @ `adbdd17` (10 Dec 2024) | Text `NULL` loaded as null. Columns typed to the spec. FOCUS 1.5 columns added, null where 1.0 has no equivalent. `ServiceProviderName` and `HostProviderName` derived using the spec's version migration guidance. `Id` renamed `x_SampleRowId`. |
| `focus/data/cau_examples.parquet`, `SkuPrice.parquet`, `InvoiceDetail.parquet`, `ContractCommitment.parquet`, `CorrectionExamples.parquet` | [FOCUS_Spec](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec), worked-example CSVs in `specification/data/` | `working_draft` @ `e9cdcc7` (3 Nov 2026) | Files combined per dataset, with `x_ExampleFile` recording each row's source file. Text `null` and currency-formatted numbers (such as `$10,000.00`) cleaned. Columns typed to the spec. |
| `focus/data/manifest.json` | Generated from the files above | as above | Table list, row counts and column types |
| `focus/spec-queries.json` | FOCUS_Spec, example SQL in `specification/supported_features/*.md` and `supporting_content/appendix/version_migration_guidance.md` | `working_draft` @ `e9cdcc7` | Converted from BigQuery SQL to DuckDB SQL with sqlglot. `?` placeholders filled with values from the data. Notes added for the 3 queries that don't run in DuckDB as published. |
| `focus/model.json` | FOCUS_Spec, dataset and column definitions in `specification/datasets/` | `working_draft` @ `e9cdcc7` | Definitions extracted and Markdown links removed. Relationships written out from each dataset's Relationships section and two Invoice Detail column definitions. Each relationship records its source file. |

The empty `BillingPeriod` table is created in the browser from the column definitions in `focus/model.json`.

## Libraries loaded at runtime

These are loaded from jsDelivr when the page runs. They are not stored in this repository.

| Library | Version | Licence |
| --- | --- | --- |
| [DuckDB-WASM](https://github.com/duckdb/duckdb-wasm) | 1.33.1-dev57.0 | MIT |
| [Perspective](https://github.com/finos/perspective) (FINOS) | 3.8.0 | Apache 2.0 |
