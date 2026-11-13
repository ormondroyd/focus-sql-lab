# Notice

FOCUS SQL Lab is an independent project. It is not affiliated with or endorsed by the FinOps Foundation, the
FOCUS project, the Joint Development Foundation or the Linux Foundation.

## What is original to this project

Everything outside `site/focus/`:

- `site/index.html`: the page (query editor, response explorer, data model view)
- `site/lab-setup.sql`: what the lab adds to DuckDB so the specification's queries run as published
- `site/column-notes.json`: notes on the debate behind the 11 join-key columns, written by an AI model from
  the FOCUS_Spec GitHub issues and pull requests each note lists. They paraphrase those discussions and name
  participants by their GitHub usernames.
- `site/evidence.json`: evidence items curated by an AI model from FOCUS_Spec issues and the conversation
  summaries; quotes are verbatim from the issue named, and organisations are named only as the issues name them.
- `site/object-summaries.json`: plain-language summaries of the specification's dataset, column, attribute, appendix, metadata and schema pages,
  written by an AI model from each page at `working_draft` @ `e9cdcc7`. They paraphrase the specification.
- `site/thread-summaries.json`: summaries of the conversation in the FOCUS_Spec issues and pull requests shown in the
  Data model's history that have three or more comments or reviews, written by an AI model from each thread.
  They paraphrase those discussions and name participants by their GitHub usernames.
- `site/recent.json`: the FOCUS_Spec issues and pull requests people opened, commented on or reviewed in the last two
  weeks, rebuilt daily from GitHub: titles, links, authors, dates, labels, status changes posted by the repository's
  automation, short plain-text excerpts of each comment and review, and a summary of each thread's fortnight and a
  one-line gist of each comment and review, written by an AI model. They paraphrase those discussions and name
  participants by their GitHub usernames.
- `site/update-log.json`: the record of each rebuild and each batch of AI-written text, with counts and costs.
- `tools/practice.json`: the practice queries, which are built into `site/practice-queries.json`
- `tools/*.py`: the build scripts
- `Dockerfile`, `nginx.conf`, `README.md`, `NOTICE.md`

Licences for this original material:

- **Code** (`site/index.html`, `site/lab-setup.sql`, `tools/`, `Dockerfile`, `nginx.conf`): the
  [Apache License 2.0](LICENSE).
- **Writing and curated content** (`site/object-summaries.json`, `site/thread-summaries.json`,
  `site/column-notes.json`, `site/evidence.json`, `tools/practice.json`, `findings/`, `README.md`, `BACKLOG.md`,
  `NOTICE.md`): [Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
  Short quotations from FOCUS_Spec issues inside `site/evidence.json` remain their authors' and are quoted with
  links to their source.

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
| `focus/history.json` | FOCUS_Spec git history (commits that changed each definition file, following renames) and its pull requests and issues on GitHub, including pull requests that were never merged, matched by the files they changed | history up to `working_draft` @ `e9cdcc7`; GitHub status as of the build date | For each pull request: title, link, author, merge date, files changed, comment and review counts, and an excerpt of its description (or its issue's, where it has none), cut at a sentence end with Markdown link and emphasis marks removed. For each issue: title, link and comment count. For both: GitHub status (merged, open, or closed with its reason) and the date it closed. For each requirement line: the pull request that last changed it, from git blame. |
| `focus/ai-tokens.json` | FOCUS_Spec, the AI Model Billing supported feature, the SkuPriceDetails column (its AI model and token properties and the note on them) and one glossary sentence, from `specification/`; FOCUS_Spec issues and pull requests on GitHub | `working_draft` @ `e9cdcc7`; GitHub status as of the build date | Specification text quoted verbatim. For each listed issue and pull request: title, link, status, and the dates it opened and closed. The explanations, and which threads are listed under each gap, are the lab's. |
| `focus/refresh.json` | FOCUS_Spec: the `working_draft` commit the site was built from (from `focus/model.json`) | as built | The commit and its date, the date of the last rebuild, and the dates the AI summaries were last written. |
| `focus/model.json` | FOCUS_Spec, dataset, column and attribute definitions, allowed values, operating model conditions, the glossary, and the appendix, metadata and JSON schema pages (the schemas kept verbatim), from `specification/` | `working_draft` @ `e9cdcc7` | Definitions extracted and Markdown links removed, except in each Requirements section, which is kept line for line as written. Relationships written out from each dataset's Relationships section and two Invoice Detail column definitions. Each relationship records its source file. |

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
