"""Build the FOCUS SQL Lab's Parquet tables.

Usage: python -I build_data.py <FOCUS_Spec clone> <raw data dir> <output dir>

Tables
  cau_real            FOCUS-Sample-Data 1.0 (anonymised real billing, 100k rows),
                      typed and given FOCUS 1.5 column names where a mapping exists
  cau_examples        FOCUS 1.5 worked-example Cost and Usage rows from the spec
  ContractCommitment, InvoiceDetail, SkuPrice   1.5 worked examples
  CorrectionExamples  correction-handling worked examples (ledger/delta/replacement)
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
    """Add every 1.5 column the table lacks, as a typed NULL, so spec queries bind."""
    have = {r[0].lower() for r in con.execute(f"DESCRIBE {table}").fetchall()}
    for low, (name, ftype) in TYPES[dataset].items():
        if low not in have:
            con.execute(f'ALTER TABLE {table} ADD COLUMN "{name}" {SQL_TYPE[ftype]}')


manifest = {"tables": {}}

# ---- Real data: FOCUS-Sample-Data 1.0, anonymised ---------------------------------
raw_csv = RAW / "focus_sample_100000.csv.gz"
con.execute(
    f"CREATE TABLE raw_real AS SELECT * FROM read_csv('{raw_csv}', all_varchar=true, "
    f"nullstr='NULL', header=true, quote='\"', escape='\"', max_line_size=10000000)"
)
parts, cols = typed_select("raw_real", "CostAndUsage")
parts = [p if p != '"Id"' else '"Id" AS x_SampleRowId' for p in parts]
con.execute(f"CREATE TABLE cau_real AS SELECT {', '.join(parts)} FROM raw_real")
lost = check_casts("raw_real", "cau_real", [c for c in cols if c.lower() in TYPES["CostAndUsage"]])
# 1.0 -> 1.5 provider mapping from the spec's version migration guidance
con.execute("ALTER TABLE cau_real ADD COLUMN ServiceProviderName VARCHAR")
con.execute("ALTER TABLE cau_real ADD COLUMN HostProviderName VARCHAR")
# Direct purchase (publisher blank, or the provider itself, or the invoicing entity): service provider = CSP.
# Otherwise it's a marketplace purchase: service provider = the publisher (e.g. Red Hat, Datadog on AWS).
con.execute("""UPDATE cau_real SET
    ServiceProviderName = CASE WHEN PublisherName IS NULL OR PublisherName = ProviderName
                                    OR PublisherName = InvoiceIssuerName THEN ProviderName
                               ELSE PublisherName END,
    HostProviderName = ProviderName""")
add_missing("cau_real", "CostAndUsage")
con.execute("ALTER TABLE cau_real ADD COLUMN x_Dataset VARCHAR DEFAULT 'FOCUS-Sample-Data 1.0 (anonymised real)'")
print("cau_real rows:", con.execute("SELECT count(*) FROM cau_real").fetchone()[0], "cast losses:", lost)

# ---- 1.5 worked examples from the spec --------------------------------------------
DATA = SPEC / "specification/data"
groups = {
    "cau_examples": ("CostAndUsage", [p for p in DATA.rglob("*.csv") if p.parts[len(DATA.parts)] not in
                                      ("contract_commitments", "invoice_detail", "sku_price_examples",
                                       "correction-handling-examples")]),
    "ContractCommitment": ("ContractCommitment", sorted((DATA / "contract_commitments").glob("*.csv"))),
    "InvoiceDetail": ("InvoiceDetail", sorted((DATA / "invoice_detail").glob("*.csv"))),
    "SkuPrice": ("SkuPrice", sorted((DATA / "sku_price_examples").glob("*.csv"))),
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
    add_missing(table, dataset)
    print(f"{table} rows:", con.execute(f"SELECT count(*) FROM {table}").fetchone()[0],
          "files:", len(files), "cast losses:", lost)

# ---- Write Parquet + manifest --------------------------------------------------------
DESCRIPTIONS = {
    "cau_real": "Anonymised real FOCUS 1.0 billing data (AWS, Microsoft, Oracle), 100,000 rows from "
                "FinOps Foundation FOCUS-Sample-Data, with FOCUS 1.5 column names added. 1.5-only columns are NULL.",
    "cau_examples": "FOCUS 1.5 worked-example Cost and Usage rows from the specification (AI tokens, prompt caching, "
                    "commitments, SaaS). Each scenario is separate: filter by x_ExampleFile before summing.",
    "ContractCommitment": "FOCUS 1.5 Contract Commitment worked examples.",
    "InvoiceDetail": "FOCUS 1.5 Invoice Detail worked examples.",
    "SkuPrice": "FOCUS 1.5 SKU Price (preview) worked examples.",
    "CorrectionExamples": "FOCUS correction-handling worked examples (original, delta, ledger, replacement files).",
}
for table in ["cau_real", "cau_examples", "ContractCommitment", "InvoiceDetail", "SkuPrice", "CorrectionExamples"]:
    path = OUT / f"{table}.parquet"
    con.execute(f"COPY {table} TO '{path}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 20000)")
    columns = [{"name": r[0], "type": r[1]} for r in con.execute(f"DESCRIBE {table}").fetchall()]
    rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    manifest["tables"][table] = {"file": path.name, "rows": rows, "bytes": path.stat().st_size,
                                 "description": DESCRIPTIONS[table], "columns": columns}
    print(f"wrote {path.name}: {rows} rows, {path.stat().st_size:,} bytes, {len(columns)} columns")

(OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
