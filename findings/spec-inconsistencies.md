# Inconsistencies in the FOCUS specification's examples

Found while building this lab against the FOCUS_Spec `working_draft` at `e9cdcc7` (the 1.5 candidate, November 2026),
then re-checked against the page text.

**Status (checked 14 November 2026): the maintainers are already fixing all four confirmed findings**, in the editorial
clean-up for the 1.5 release, which followed a review of the full 1.5 specification on 4 November:
[issue #2832](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/issues/2832) and [pull request #2846](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/pull/2846) correct the contract period examples (finding 1,
including a link in Contract Commitment Period End that pointed at Contract Period Start), and
[issue #2834](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/issues/2834) and [pull request #2869](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/pull/2869) correct the metadata examples (findings 3 to 5).
Both pull requests were open when checked. The systemic fix below, issue #1974, is still open.

Why examples matter: the specification explains many rules with worked examples (for example, sample dates to show what
"inclusive start, exclusive end" means, or sample metadata to show its structure). Implementers learn from and copy
these examples, so an example that contradicts its own rule teaches the rule wrongly.

## The findings, stress-tested

| # | What looks wrong | Situation | Complication | Impact | Holds up? |
|---|---|---|---|---|---|
| 1 | The contract period examples describe the wrong period | Four contract column pages each use a short example to explain where a period starts and stops | The examples mix two periods: one example lasts a day but refers to a date a year later; another lasts a year but refers to the wrong day | A reader learning the start and stop rule from the example is confused by the thing it exists to teach | Yes: re-read all four pages word for word |
| 2 | The commitment discount examples may disagree about unused commitment rows | The appendix walks through worked examples of reservations and savings plans | It was reported that the overview leaves the resource field empty on unused rows while the detailed tables fill it in | It would leave providers unsure what to put in that field | Not confirmed: that wording was not found in the overview, and the detailed tables match the rules |
| 3 | A metadata example names the wrong column | An example shows how to record a change to a column's data type | The text says column 1 changed, then refers to "the modification to" column 2 | Minor confusion about which column changed | Yes, but a typo rather than a substantive contradiction |
| 4 | The recency examples use field names that don't exist | Recency metadata says how up to date a delivery is, in a field the spec names `RecencyLastUpdated` | The examples use `RecencyLastUpdateDate` and `RecencyLastUpdate`, and contain an impossible date (`2025-01-291`) | Copying the example produces metadata a validator should reject | Yes: in two example files |
| 5 | One metadata example uses an undefined field name | Thirteen metadata examples use `ProviderTagPrefixes` | One uses `DataGeneratorTagPrefixes`, which the spec does not define | Copying the example produces invalid metadata | Yes: 1 of 14 examples |

## What would fix them

| # | Proposal | Action | Benefit | Where |
|---|---|---|---|---|
| 1 | Make each example describe one consistent period | A small errata pull request correcting the example dates | The rule becomes teachable from its own example | [ContractPeriodEnd](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/blob/working_draft/specification/datasets/contract_commitment/columns/contractperiodend.md), and ContractPeriodStart, ContractCommitmentPeriodStart and ContractCommitmentPeriodEnd |
| 2 | Verify before acting | Read the overview by hand; raise it only if the conflict is real | Avoids reporting something that isn't wrong | [Commitment discount examples](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/blob/working_draft/specification/appendix/commitment_discounts/commitment_discounts.md) |
| 3 | Correct the column name | A one-word fix | Clarity | [Changing column metadata example](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/blob/working_draft/specification/appendix/metadata_examples/changing_column_metadata_example.md) |
| 4 | Use the defined field name and a valid date | A small errata pull request | Examples that would pass a validator | [Recency metadata example](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/blob/working_draft/specification/appendix/metadata_examples/recency_metadata_example.md) |
| 5 | Use `ProviderTagPrefixes` | A one-word fix | Consistency across all 14 examples | [Data generator version example](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/blob/working_draft/specification/appendix/metadata_examples/data_generator_version_changed_example.md) |

## The systemic fix

Findings 4 and 5 are errors an automated check would catch: the examples use field names the specification doesn't
define. FOCUS_Spec issue [#1974](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/issues/1974), that the
specification's examples should pass the validator (milestone 1.6), is the fix for this whole class of error: check
every example automatically rather than finding mistakes one at a time.

## Related: proposed sample data

In the FOCUS 1.4 sample data proposed in FOCUS-Sample-Data
[pull request #5](https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data/pull/5) (a draft), all 1,000
`ReferenceInvoiceId` values match no invoice, though the specification requires each to match the adjusted invoice or
the row's own. The lab's Data model shows this under that data source.
