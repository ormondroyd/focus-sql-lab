# Backlog

The next things to build.

## 1. Refresh automatically

Today the site refreshes only when someone reruns the four build scripts and pushes.

- A scheduled job (for example a weekly GitHub Action) updates the FOCUS_Spec clones, reruns `build_data.py`,
  `extract_sql.py`, `extract_model.py` and `extract_history.py` against the latest `working_draft` commit, and pushes
  if anything changed. Coolify redeploys on push.
- Summaries are regenerated on change, not wholesale: record a hash of each spec page and each thread the summaries were
  written from, and write new summaries only for pages and threads that are new or have changed
  (`object-summaries.json`, `thread-summaries.json`). This is the only step that needs an AI model.
- The page says when the data and the summaries were last refreshed.

Done when a new pull request or a changed spec page appears on the site, summarised, without anyone running a script.

## 2. AI tokens view

One place that shows how FOCUS models AI token usage today, and where it stops.

- The columns and `SkuPriceDetails` keys involved (model, token direction, cache action), with definitions.
- The spec's AI appendix examples, the worked-example rows and the token queries.
- The threads that shaped them (for example #2018, #2099, #2442, #2606).
- Gaps, stated plainly: token properties live inside a JSON column rather than as columns; no column measures energy, so
  "tokens per watt" has nowhere to go; "cost per intelligence" needs outcome data that billing doesn't carry; public
  token data is limited to the spec's own examples.

## 3. Customer evidence view

Pull the product evidence out of the issues and threads: problem statements and what they cost practitioners, who asked
for a change, how the working group found out (surveys, polls, user groups, provider outreach, finance specialists),
use cases, and the trade-offs behind what was cut or deferred. A first keyword pass finds about 150 candidate
statements; curate them into a browsable list linked to their threads.

## 4. Metadata

The FOCUS metadata section (data generator, dataset instance, recency, schema) describes a delivery of FOCUS data
rather than its rows. Add it to the Data model with definitions and requirements, the same way as datasets.

## 5. Appendix examples in context

Link the spec's appendix examples (discount handling, split cost allocation, invoice and billing period handling,
rounding tolerance, AI billing and caching) from the columns and attributes they illustrate.

## 6. Licensing mapping experiment

Generate synthetic software-licensing data (entitlements, subscription and support terms, part numbers, processor- or
user-based metrics, sub-capacity usage), express it in FOCUS (for example part number as `SkuId`, licence metric as
`PricingUnit`, entitlements as Contract Commitment rows), and run the spec's queries against it to show where FOCUS fits
licensing and where it strains. Licensing is a scope area FOCUS lists as under development.

## Open questions

- Keep the 1.0 sample mapped to FOCUS 1.5 with its 1.5-only columns empty, or drop those columns, or show it as plain 1.0?
- Choose a licence for the original files (everything outside `site/focus/`).
