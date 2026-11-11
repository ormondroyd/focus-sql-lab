# Notice

FOCUS SQL Lab is an independent project. It is not affiliated with or endorsed by the FinOps Foundation, the
FOCUS project, the Joint Development Foundation or the Linux Foundation.

## What is original to this project

Everything outside `site/focus/`:

- `site/index.html`: the page (query editor, response explorer, data model view)
- `site/lab-setup.sql`: what the lab adds to DuckDB so the specification's queries run as published
- `site/column-notes.json`: notes on the debate behind the 11 join-key columns, written by Claude (an AI model) from
  the FOCUS_Spec GitHub issues and pull requests each note lists. They paraphrase those discussions and name
  participants by their GitHub usernames.
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
| `focus/data/cau_pr7.parquet`, `cc_pr7.parquet` | FOCUS-Sample-Data [pull request #7](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/pull/7) by guymano (open, not merged), `FOCUS-1.3/focus_sample_costandusage_{aws,azure,gcp}_1000.csv` and `focus_sample_contractcommitment_{aws,azure,gcp}.csv` | `guymano/FOCUS-Sample-Data` @ `9991701` (5 Sep 2026) | The three providers' files combined per dataset. Columns typed to the FOCUS 1.5 types. FOCUS 1.5 columns the files lack added, empty. Values unchanged. |
| `focus/data/cau_pr5.parquet`, `cc_pr5.parquet`, `inv_pr5.parquet`, `bp_pr5.parquet` | FOCUS-Sample-Data [pull request #5](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/pull/5) by beau-finopsorg (draft, not merged), `FOCUS-1.4/focus_sample_{costandusage,contractcommitment,invoicedetail,billingperiod}.csv` | `beau-finopsorg/FOCUS-Sample-Data` @ `4fe60d9` (18 Jun 2026) | Columns typed to the FOCUS 1.5 types. FOCUS 1.5 columns the files lack added, empty. Values unchanged. |
| `focus/data/cau_examples.parquet`, `sku_examples.parquet`, `inv_examples.parquet`, `cc_examples.parquet`, `CorrectionExamples.parquet` | [FOCUS_Spec](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec), worked-example CSVs in `specification/data/` | `working_draft` @ `e9cdcc7` (3 Nov 2026) | Files combined per dataset, with `x_ExampleFile` recording each row's source file. Text `null` and currency-formatted numbers (such as `$10,000.00`) cleaned. Columns typed to the spec. |
| `focus/data/manifest.json` | Generated from the files above | as above | Table list, row counts, column types, the columns the lab added or derived with the reason for each, and the data sources (which table each FOCUS dataset name points to) |
| `focus/spec-queries.json` | FOCUS_Spec, example SQL in `specification/supported_features/*.md` and `supporting_content/appendix/version_migration_guidance.md` | `working_draft` @ `e9cdcc7` | Query text copied verbatim. A suggested value and type added for each `?` input. Test results added, and notes for the 4 queries that don't run in DuckDB as published. |
| `focus/history.json` | FOCUS_Spec git history (commits that changed each definition file, following renames) and its pull requests and issues on GitHub | history up to `working_draft` @ `e9cdcc7` | For each pull request: title, link, author, merge date, files changed, comment and review counts, and an excerpt of its description (or its issue's, where it has none), cut at a sentence end with Markdown link and emphasis marks removed. For each issue: title, link and comment count. |
| `focus/model.json` | FOCUS_Spec, dataset and column definitions in `specification/datasets/` | `working_draft` @ `e9cdcc7` | Definitions extracted and Markdown links removed. Relationships written out from each dataset's Relationships section and two Invoice Detail column definitions. Each relationship records its source file. |

FOCUS-Sample-Data is licensed under CC BY 4.0. The two pull requests propose files for that repository; neither has
been merged, and FOCUS has not accepted either sample.

Where a data source has no data for a dataset, an empty table is created in the browser from the column definitions in
`focus/model.json`.

## Libraries loaded at runtime

These are loaded from jsDelivr when the page runs. They are not stored in this repository.

| Library | Version | Licence |
| --- | --- | --- |
| [DuckDB-WASM](https://github.com/duckdb/duckdb-wasm) | 1.33.1-dev57.0 | MIT |
| [Perspective](https://github.com/finos/perspective) (FINOS) | 3.8.0 | Apache 2.0 |
