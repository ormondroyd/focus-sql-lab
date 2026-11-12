# Backlog

The next things to build.

## 1. Refresh automatically

Today the site refreshes only when someone reruns the five build scripts and pushes.

- A scheduled job (for example a weekly GitHub Action) updates the FOCUS_Spec clones, reruns `build_data.py`,
  `extract_sql.py`, `extract_model.py`, `extract_history.py` and `extract_ai.py` against the latest `working_draft` commit, and pushes
  if anything changed. Coolify redeploys on push.
- Summaries are regenerated on change, not wholesale: record a hash of each spec page and each thread the summaries were
  written from, and write new summaries only for pages and threads that are new or have changed
  (`object-summaries.json`, `thread-summaries.json`). This is the only step that needs an AI model.
- The page says when the data and the summaries were last refreshed.

Done when a new pull request or a changed spec page appears on the site, summarised, without anyone running a script.

## 2. Licensing mapping experiment

Generate synthetic software-licensing data (entitlements, subscription and support terms, part numbers, processor- or
user-based metrics, sub-capacity usage), express it in FOCUS (for example part number as `SkuId`, licence metric as
`PricingUnit`, entitlements as Contract Commitment rows), and run the spec's queries against it to show where FOCUS fits
licensing and where it strains. Licensing is a scope area FOCUS lists as under development.

## Open questions

- Keep the 1.0 sample mapped to FOCUS 1.5 with its 1.5-only columns empty, or drop those columns, or show it as plain 1.0?
