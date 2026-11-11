"""Build the FOCUS SQL Lab's Parquet tables.

Usage: python -I build_data.py <FOCUS_Spec clone> <raw data dir> <output dir>

Tables
  cau_sample            FOCUS-Sample-Data 1.0 (anonymised, 100k rows),
                      typed and given FOCUS 1.5 column names where a mapping exists
  cau_examples        FOCUS 1.5 worked-example Cost and Usage rows from the spec
  cc_examples, inv_examples, sku_examples   1.5 worked-example Contract Commitment, Invoice Detail, SKU Price rows
  CorrectionExamples  correction-handling worked examples (ledger/delta/replacement)
  cau_pr7, cc_pr7     FOCUS 1.3 sample proposed in FOCUS-Sample-Data pull request #7 (not accepted)
  cau_pr5, cc_pr5, inv_pr5, bp_pr5   FOCUS 1.4 sample proposed in FOCUS-Sample-Data pull request #5 (draft, not accepted)

The manifest's "sources" say which table each FOCUS dataset name points to for each data source. The page and
extract_sql.py turn them into views, so a spec query that reads ContractCommitment reads that source's rows.
"""

import json
import pathlib
import re
import sys

import duckdb

SPEC = pathlib.Path(sys.argv[1])
RAW = pathlib.Path(sys.argv[2])
OUT = pathlib.Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)

DATASETS = {
    "CostAndUsage": "cost_and_usage",
    "ContractCommitment": "contract_commitment",
    "InvoiceDetail": "invoice_detail",
    "SkuPrice": "sku_price",
    "BillingPeriod": "billing_period",
}
SQL_TYPE = {"String": "VARCHAR", "Decimal": "DOUBLE", "Date/Time": "TIMESTAMP", "JSON": "VARCHAR"}


def column_types(dataset_dir):
    """Map lower-case column id -> (Column id, FOCUS data type) from the spec's column pages."""
    out = {}
    for md in sorted((SPEC / "specification/datasets" / dataset_dir / "columns").glob("*.md")):
        text = md.read_text()
        dtype = re.search(r"^\|\s*Data type\s*\|\s*([^|]+?)\s*\|", text, re.M)
        col_id = re.search(r"^## Column ID\s*\n+\s*`?([A-Za-z0-9_]+)`?\s*$", text, re.M)
        if dtype:
            name = col_id.group(1) if col_id else md.stem
            out[md.stem.lower()] = (name, dtype.group(1))
    return out


TYPES = {ds: column_types(d) for ds, d in DATASETS.items()}

con = duckdb.connect()


def typed_select(table, dataset, keep_extra=True):
    """SELECT list that casts every known FOCUS column to its spec type."""
    cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    known = TYPES[dataset]
    parts = []
    for c in cols:
        spec = known.get(c.lower())
        if spec is None:
            if keep_extra:
                parts.append(f'"{c}"')
            continue
        name, ftype = spec
        # Some spec example files hold the literal text "null" instead of an empty field.
        v = f"NULLIF(NULLIF(lower(trim(\"{c}\")), 'null'), '')"
        if ftype == "Decimal":
            # ...and some hold currency-formatted text such as "$10,000.00 " in Decimal columns.
            parts.append(f"TRY_CAST(replace(replace({v}, '$', ''), ',', '') AS DOUBLE) AS \"{name}\"")
        elif ftype == "Date/Time":
            parts.append(f"TRY_CAST(replace(replace(upper({v}), 'T', ' '), 'Z', '') AS TIMESTAMP) AS \"{name}\"")
        else:
            parts.append(f"CASE WHEN {v} IS NULL THEN NULL ELSE \"{c}\" END AS \"{name}\"")
    return parts, cols


def check_casts(src, dst, cols):
    """Report any value that was present before the cast and NULL after it."""
    lost = []
    for c in cols:
        try:
            n = con.execute(
                f'SELECT count(*) FROM (SELECT row_number() OVER () rn, "{c}" v FROM {src}) a '
                f'JOIN (SELECT row_number() OVER () rn, "{c}" v FROM {dst}) b USING (rn) '
                f"WHERE a.v IS NOT NULL AND trim(a.v) <> '' AND lower(trim(a.v)) <> 'null' AND b.v IS NULL"
            ).fetchone()[0]
        except duckdb.Error:
            continue
        if n:
            lost.append((c, n))
    return lost


def add_missing(table, dataset):
    """Add every 1.5 column the table lacks, as a typed NULL, so spec queries bind. Returns the names added."""
    have = {r[0].lower() for r in con.execute(f"DESCRIBE {table}").fetchall()}
    added = []
    for low, (name, ftype) in TYPES[dataset].items():
        if low not in have:
            con.execute(f'ALTER TABLE {table} ADD COLUMN "{name}" {SQL_TYPE[ftype]}')
            added.append(name)
    return added


manifest = {"tables": {}}
# Columns this lab added, renamed or derived, with the reason: shown on the page so they're never mistaken for FOCUS data.
LAB_COLUMNS = {}

# ---- Sample data: FOCUS-Sample-Data 1.0, anonymised ---------------------------------
raw_csv = RAW / "focus_sample_100000.csv.gz"
con.execute(
    f"CREATE TABLE raw_sample AS SELECT * FROM read_csv('{raw_csv}', all_varchar=true, "
    f"nullstr='NULL', header=true, quote='\"', escape='\"', max_line_size=10000000)"
)
parts, cols = typed_select("raw_sample", "CostAndUsage")
parts = [p if p != '"Id"' else '"Id" AS x_SampleRowId' for p in parts]
con.execute(f"CREATE TABLE cau_sample AS SELECT {', '.join(parts)} FROM raw_sample")
lost = check_casts("raw_sample", "cau_sample", [c for c in cols if c.lower() in TYPES["CostAndUsage"]])
# 1.0 -> 1.5 provider mapping from the spec's version migration guidance
con.execute("ALTER TABLE cau_sample ADD COLUMN ServiceProviderName VARCHAR")
con.execute("ALTER TABLE cau_sample ADD COLUMN HostProviderName VARCHAR")
# Direct purchase (publisher blank, or the provider itself, or the invoicing entity): service provider = CSP.
# Otherwise it's a marketplace purchase: service provider = the publisher (e.g. Red Hat, Datadog on AWS).
con.execute("""UPDATE cau_sample SET
    ServiceProviderName = CASE WHEN PublisherName IS NULL OR PublisherName = ProviderName
                                    OR PublisherName = InvoiceIssuerName THEN ProviderName
                               ELSE PublisherName END,
    HostProviderName = ProviderName""")
added = add_missing("cau_sample", "CostAndUsage")
con.execute("ALTER TABLE cau_sample ADD COLUMN x_Dataset VARCHAR DEFAULT 'FOCUS-Sample-Data 1.0 (anonymised)'")
LAB_COLUMNS["cau_sample"] = {
    "x_SampleRowId": "The sample's own row ID column, Id, renamed by the lab. It isn't a FOCUS column.",
    "ServiceProviderName": "Derived by the lab from ProviderName, PublisherName and InvoiceIssuerName, following the "
                           "spec's version migration guidance. FOCUS 1.0 has no such column.",
    "HostProviderName": "Derived by the lab from ProviderName, following the spec's version migration guidance. "
                        "FOCUS 1.0 has no such column.",
    "x_Dataset": "Added by the lab: names the source dataset.",
    **{c: "Added empty by the lab: a FOCUS 1.5 column that FOCUS 1.0 doesn't have." for c in added
       if c not in ("ServiceProviderName", "HostProviderName")},
}
print("cau_sample rows:", con.execute("SELECT count(*) FROM cau_sample").fetchone()[0], "cast losses:", lost)

# ---- 1.5 worked examples from the spec --------------------------------------------
DATA = SPEC / "specification/data"
groups = {
    "cau_examples": ("CostAndUsage", [p for p in DATA.rglob("*.csv") if p.parts[len(DATA.parts)] not in
                                      ("contract_commitments", "invoice_detail", "sku_price_examples",
                                       "correction-handling-examples")]),
    "cc_examples": ("ContractCommitment", sorted((DATA / "contract_commitments").glob("*.csv"))),
    "inv_examples": ("InvoiceDetail", sorted((DATA / "invoice_detail").glob("*.csv"))),
    "sku_examples": ("SkuPrice", sorted((DATA / "sku_price_examples").glob("*.csv"))),
    "CorrectionExamples": ("CostAndUsage", sorted((DATA / "correction-handling-examples").rglob("*.csv"))),
}
for table, (dataset, files) in groups.items():
    files = sorted(files)
    flist = "[" + ", ".join(f"'{f}'" for f in files) + "]"
    con.execute(
        f"CREATE TABLE raw_{table} AS SELECT * FROM read_csv({flist}, all_varchar=true, header=true, "
        f"union_by_name=true, filename=true)"
    )
    # strip any UTF-8 BOM that survived into a header
    for (c,) in con.execute(f"SELECT column_name FROM (DESCRIBE raw_{table})").fetchall():
        if c.startswith("﻿"):
            con.execute(f'ALTER TABLE raw_{table} RENAME COLUMN "{c}" TO "{c[1:]}"')
    parts, cols = typed_select(f"raw_{table}", dataset)
    parts = [p for p in parts if p != '"filename"']
    rel = f"replace(filename, '{DATA}/', '')"
    con.execute(f"CREATE TABLE {table} AS SELECT {', '.join(parts)}, {rel} AS x_ExampleFile FROM raw_{table}")
    lost = check_casts(f"raw_{table}", table, [c for c in cols if c.lower() in TYPES[dataset]])
    added = add_missing(table, dataset)
    LAB_COLUMNS[table] = {
        "x_ExampleFile": "Added by the lab: the worked-example file the row came from.",
        **{c: "Added empty by the lab: a FOCUS 1.5 column that none of these example files include." for c in added},
    }
    print(f"{table} rows:", con.execute(f"SELECT count(*) FROM {table}").fetchone()[0],
          "files:", len(files), "cast losses:", lost)

# ---- Proposed samples from open FOCUS-Sample-Data pull requests (not accepted by FOCUS) --------------------
# Read as published at each pull request's head commit, typed to the FOCUS 1.5 column types. Values are unchanged.
PROPOSED = {
    "pr7": ("FOCUS 1.3", RAW / "pr7-1.3", {
        "cau_pr7": ("CostAndUsage", "focus_sample_costandusage_*_1000.csv"),
        "cc_pr7": ("ContractCommitment", "focus_sample_contractcommitment_*.csv")}),
    "pr5": ("FOCUS 1.4", RAW / "pr5-1.4", {
        "cau_pr5": ("CostAndUsage", "focus_sample_costandusage.csv"),
        "cc_pr5": ("ContractCommitment", "focus_sample_contractcommitment.csv"),
        "inv_pr5": ("InvoiceDetail", "focus_sample_invoicedetail.csv"),
        "bp_pr5": ("BillingPeriod", "focus_sample_billingperiod.csv")}),
}
for src, (version, folder, tables) in PROPOSED.items():
    for table, (dataset, pattern) in tables.items():
        files = sorted(folder.glob(pattern))
        assert files, (table, pattern)
        flist = "[" + ", ".join(f"'{f}'" for f in files) + "]"
        con.execute(f"CREATE TABLE raw_{table} AS SELECT * FROM read_csv({flist}, all_varchar=true, header=true, "
                    f"union_by_name=true)")
        parts, cols = typed_select(f"raw_{table}", dataset)
        con.execute(f"CREATE TABLE {table} AS SELECT {', '.join(parts)} FROM raw_{table}")
        lost = check_casts(f"raw_{table}", table, [c for c in cols if c.lower() in TYPES[dataset]])
        extra = [c for c in cols if c.lower() not in TYPES[dataset]]
        added = add_missing(table, dataset)
        LAB_COLUMNS[table] = {c: f"Added empty by the lab: a FOCUS 1.5 column that this {version} sample doesn't have."
                              for c in added}
        print(f"{table} rows:", con.execute(f"SELECT count(*) FROM {table}").fetchone()[0], "files:", len(files),
              "cast losses:", lost, "not in 1.5:", extra, "added:", len(added))

# ---- Write Parquet + manifest --------------------------------------------------------
DESCRIPTIONS = {
    "cau_sample": "Anonymised FOCUS 1.0 data (AWS, Microsoft, Oracle), 100,000 rows from "
                "FinOps Foundation FOCUS-Sample-Data, with FOCUS 1.5 column names added. 1.5-only columns are NULL.",
    "cau_examples": "FOCUS 1.5 worked-example Cost and Usage rows from the specification (AI tokens, prompt caching, "
                    "commitments, SaaS). Each scenario is separate: filter by x_ExampleFile before summing.",
    "cc_examples": "FOCUS 1.5 Contract Commitment worked examples from the specification.",
    "inv_examples": "FOCUS 1.5 Invoice Detail worked examples from the specification.",
    "sku_examples": "FOCUS 1.5 SKU Price (preview) worked examples from the specification.",
    "CorrectionExamples": "FOCUS correction-handling worked examples (original, delta, ledger, replacement files).",
    "cau_pr7": "Synthetic FOCUS 1.3 Cost and Usage data for AWS, Azure and Google Cloud (1,000 rows each), proposed in "
               "FOCUS-Sample-Data pull request #7. Not accepted by FOCUS.",
    "cc_pr7": "Synthetic FOCUS 1.3 Contract Commitment data for AWS, Azure and Google Cloud, proposed in "
              "FOCUS-Sample-Data pull request #7. Not accepted by FOCUS.",
    "cau_pr5": "Generated FOCUS 1.4 Cost and Usage data (AWS, Microsoft, Google, Oracle), proposed in draft "
               "FOCUS-Sample-Data pull request #5. Its README says this file hasn't been validated. Not accepted by FOCUS.",
    "cc_pr5": "Generated FOCUS 1.4 Contract Commitment data, proposed in draft FOCUS-Sample-Data pull request #5. "
              "Not accepted by FOCUS.",
    "inv_pr5": "Generated FOCUS 1.4 Invoice Detail data, proposed in draft FOCUS-Sample-Data pull request #5. "
               "Not accepted by FOCUS.",
    "bp_pr5": "Generated FOCUS 1.4 Billing Period data, proposed in draft FOCUS-Sample-Data pull request #5. "
              "Not accepted by FOCUS.",
}
SAMPLE_REPO = "https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS-Sample-Data"
# Which table each FOCUS dataset name points to, per data source. A dataset a source doesn't have is left empty.
manifest["sources"] = {
    "sample": {"abbr": "1.0 sample", "label": "FOCUS-Sample-Data 1.0, accepted", "short": "the 1.0 sample", "status": "accepted",
               "about": "The FinOps Foundation's accepted sample: anonymised FOCUS 1.0 Cost and Usage data. FOCUS 1.0 "
                        "has no other datasets. The lab added the 1.5-only columns, empty.",
               "url": SAMPLE_REPO + "/tree/main/FOCUS-1.0",
               "tables": {"CostAndUsage": "cau_sample"}},
    "pr7": {"abbr": "1.3 PR #7", "label": "FOCUS 1.3, proposed in Sample-Data PR #7", "short": "the proposed 1.3 sample (PR #7)",
            "status": "proposed",
            "about": "Proposed, not accepted by FOCUS: synthetic FOCUS 1.3 data from an open pull request. FOCUS 1.3 "
                     "added Contract Commitment; Invoice Detail and Billing Period came in 1.4.",
            "url": SAMPLE_REPO + "/pull/7", "commit": "guymano/FOCUS-Sample-Data@99917010b27f7c0ca3586f8e0daab7e1c8103dac",
            "tables": {"CostAndUsage": "cau_pr7", "ContractCommitment": "cc_pr7"}},
    "pr5": {"abbr": "1.4 PR #5", "label": "FOCUS 1.4, proposed in Sample-Data PR #5 (draft)", "short": "the proposed 1.4 sample (PR #5)",
            "status": "proposed",
            "about": "Proposed, not accepted by FOCUS: generated FOCUS 1.4 data from an open draft pull request, "
                     "with all four 1.4 datasets.",
            "url": SAMPLE_REPO + "/pull/5", "commit": "beau-finopsorg/FOCUS-Sample-Data@4fe60d96737ea06c64851f3a0b2bcd675125b980",
            "tables": {"CostAndUsage": "cau_pr5", "ContractCommitment": "cc_pr5", "InvoiceDetail": "inv_pr5",
                       "BillingPeriod": "bp_pr5"}},
    "examples": {"abbr": "1.5 examples", "label": "Spec 1.5 worked examples", "short": "the spec 1.5 examples", "status": "spec",
                 "about": "The specification's own worked examples. Each file is its own scenario, so filter by "
                          "x_ExampleFile. The spec has no Billing Period examples.",
                 "url": "https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec/tree/working_draft/specification/data",
                 "tables": {"CostAndUsage": "cau_examples", "ContractCommitment": "cc_examples",
                            "InvoiceDetail": "inv_examples", "SkuPrice": "sku_examples"}},
}
for table in ["cau_sample", "cau_pr7", "cc_pr7", "cau_pr5", "cc_pr5", "inv_pr5", "bp_pr5",
              "cau_examples", "cc_examples", "inv_examples", "sku_examples", "CorrectionExamples"]:
    path = OUT / f"{table}.parquet"
    con.execute(f"COPY {table} TO '{path}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 20000)")
    columns = [{"name": r[0], "type": r[1]} for r in con.execute(f"DESCRIBE {table}").fetchall()]
    rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    manifest["tables"][table] = {"file": path.name, "rows": rows, "bytes": path.stat().st_size,
                                 "description": DESCRIPTIONS[table], "columns": columns,
                                 "lab_columns": LAB_COLUMNS.get(table, {})}
    print(f"wrote {path.name}: {rows} rows, {path.stat().st_size:,} bytes, {len(columns)} columns")

(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
