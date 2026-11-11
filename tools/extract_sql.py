"""Extract the FOCUS spec's example SQL, convert BigQuery SQL to DuckDB, and test each query.
Also tests the lab's own practice queries (tools/practice.json).

Usage: python -I extract_sql.py <FOCUS_Spec clone> <site dir>
Reads  <site dir>/focus/data/*.parquet
Writes <site dir>/focus/spec-queries.json   (the specification's queries, converted: FOCUS-derived)
       <site dir>/practice-queries.json     (the lab's own practice queries, with test results)
"""

import json
import pathlib
import re
import sys

import duckdb
import sqlglot

SPEC = pathlib.Path(sys.argv[1])
SITE = pathlib.Path(sys.argv[2])
DATA = SITE / "focus" / "data"

SOURCES = sorted((SPEC / "specification/supported_features").glob("*.md"))
SOURCES += [SPEC / "supporting_content/appendix/version_migration_guidance.md"]

START, END = "DATETIME '2000-01-01 00:00:00'", "DATETIME '2100-01-01 00:00:00'"


def blocks(md):
    """Yield (feature, heading, intro, sql) for every ```sql block."""
    text = md.read_text()
    feature = re.search(r"^# (.+)$", text, re.M).group(1).strip()
    heading, intro = feature, ""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^#{2,4} (.+)$", line)
        if m:
            heading, intro = m.group(1).strip(), ""
        elif line.strip().lower().startswith("```sql"):
            j = i + 1
            while not lines[j].strip().startswith("```"):
                j += 1
            yield feature, heading, intro.strip(), "\n".join(lines[i + 1:j])
            i = j
        elif line.strip() and not line.startswith("|") and not line.startswith("*"):
            intro = line.strip()
        i += 1


con = duckdb.connect()
for t in ["cau_sample", "cau_examples", "ContractCommitment", "InvoiceDetail", "SkuPrice", "CorrectionExamples"]:
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{DATA / (t + '.parquet')}'")
con.execute("CREATE VIEW CostAndUsage AS SELECT * FROM cau_examples")
con.execute("CREATE VIEW focus_data AS SELECT * FROM CostAndUsage")  # name used by the migration guide

POINT = "DATETIME '2026-03-01 00:00:00'"  # inside the Aura Web price list's effective dates
CONTRACT = "'auraweb:contract::ACCT-123456789012:agreements/ctr-7f3a91b2c4d5'"
VM_LIST_PRICE = con.execute(
    "SELECT SkuPriceId FROM SkuPrice WHERE SkuId = 'AURAWEB-COMPUTE-VM-STD-8X32' AND UnitPriceType = 'List' "
    "AND SkuPriceEffectiveStart <= TIMESTAMP '2026-03-01' AND SkuPriceEffectiveEnd IS NULL ORDER BY 1 LIMIT 1"
).fetchone()[0]
# Queries whose placeholders are whole input rows: values chosen to match the spec's Aura Web price list.
OVERRIDES = {
    "catalog_discovery_and_price_estimation-2": ["'Aura Web'", f"'{VM_LIST_PRICE}'", "720", POINT],
    "rate_optimization_and_contract_evaluation-1": ["'Aura Web'", "'Aura Web Compute'", CONTRACT, POINT],
    "rate_optimization_and_contract_evaluation-2": ["'Aura Web'", "'AURAWEB-STORAGE-OBJECT-STD'", "'us-east-1'",
                                                    "'GB-Months'", "'USD'", "100000", POINT, CONTRACT],
    "rate_optimization_and_contract_evaluation-4": ["'Aura Web'", "'AURAWEB-STORAGE-OBJECT-STD'",
                                                    "'Aura Web'", "'AURAWEB-COMPUTE-VM-STD-8X32'",
                                                    "'Aura Web'", "'AURAWEB-DATABASE-MANAGED-STD'", POINT, POINT],
    "rate_optimization_and_contract_evaluation-7": ["'Aura Web'", CONTRACT, START, END],
}
ALIASES = {"ID": "InvoiceDetail", "SP": "SkuPrice", "CU": "CostAndUsage", "CC": "ContractCommitment"}
TABLES = ["SkuPrice", "InvoiceDetail", "ContractCommitment", "CostAndUsage"]


def common_value(table, col):
    try:
        v = con.execute(f'SELECT "{col}" FROM {table} WHERE "{col}" IS NOT NULL '
                        f"GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 1").fetchone()
    except duckdb.Error:
        return None
    return None if v is None else "'" + str(v[0]).replace("'", "''") + "'"


def fill_params(sql, eid):
    """Replace each ? with a literal that suits its context. Returns (sql, notes)."""
    primary = next((t for t in TABLES if re.search(rf"\bFROM\s+{t}\b", sql)), "CostAndUsage")
    queue = list(OVERRIDES.get(eid, []))
    out, pos, notes = [], 0, []
    for m in re.finditer(r"\?", sql):
        before, after = sql[:m.start()], sql[m.end():]
        if queue:
            val = queue.pop(0)
        else:
            cm = re.search(r"(?:\b([A-Z]{2})\.)?([A-Za-z_][A-Za-z0-9_]*)\)?\s*(=|>=|<=|<>|>|<)\s*$", before)
            col, op = (cm.group(2), cm.group(3)) if cm else (None, None)
            table = ALIASES.get(cm.group(1), primary) if cm and cm.group(1) else primary
            if re.match(r"\s*IN\s+UNNEST", after):
                val = common_value("SkuPrice", "x_ExampleFile") and "'ACCT-123456789012'"
            elif col and "Effective" in col:
                val = POINT
            elif col and re.search(r"(Start|End)$", col):
                val = START if op in (">=", ">") else END
            elif col:
                val = common_value(table, col) or "NULL"
            else:
                val = "NULL"
        out.append(sql[pos:m.start()])
        out.append(val)
        notes.append(val)
        pos = m.end()
    out.append(sql[pos:])
    return "".join(out), notes


def run(sql, source):
    con.execute(f"CREATE OR REPLACE VIEW CostAndUsage AS SELECT * FROM {source}")
    try:
        rows = con.execute(sql).fetchall()
        return {"ok": True, "rows": len(rows)}
    except duckdb.Error as e:
        return {"ok": False, "error": str(e).split("\n")[0][:300]}


examples = []
for md in SOURCES:
    for n, (feature, heading, intro, raw) in enumerate(blocks(md), 1):
        eid = f"{md.stem}-{n}"
        filled, params = fill_params(raw, eid)
        try:
            duck = sqlglot.transpile(filled, read="bigquery", write="duckdb", pretty=True)[0]
            transpiled = True
        except sqlglot.errors.SqlglotError as e:
            duck, transpiled = filled, False
        sample, ex = run(duck, "cau_sample"), run(duck, "cau_examples")
        examples.append({
            "id": eid,
            "params": params,
            "feature": feature,
            "title": heading,
            "intro": intro,
            "source": str(md.relative_to(SPEC)),
            "original_sql": raw,
            "sql": duck,
            "transpiled": transpiled,
            "sample": sample,
            "examples": ex,
        })

NOTES = {
    "contract_commitments-3": "Fails in DuckDB as published. GROUP BY ContractCommitmentId binds to the "
        "CC.ContractCommitmentId column, not the SELECT alias built from JSON_VALUE(CA, ...), so that "
        "expression is not grouped. Grouping by the expression itself fixes it.",
    "custom_columns-1": "Illustrative only: x_CustomColumn stands for any provider-specific column. "
        "Replace it with an x_ column that exists to run it.",
    "data_generator_calculated_split_cost_allocation-7": "Uses JSON_TABLE(... COLUMNS (...)), SQL-standard "
        "syntax that neither BigQuery nor DuckDB supports, although the spec presents its examples as BigQuery SQL. "
        "In DuckDB, unnest the JSON array with json_extract and read each field with ->>.",
}
for e in examples:
    if e["id"] in NOTES:
        e["note"] = NOTES[e["id"]]

practice = json.loads((pathlib.Path(__file__).parent / "practice.json").read_text())
for p in practice:
    p.update({"feature": "Practice queries", "source": None, "params": [], "transpiled": False,
              "sample": run(p["sql"], "cau_sample"), "examples": run(p["sql"], "cau_examples")})
    print("practice", p["id"], "sample:", p["sample"], "examples:", p["examples"])

(SITE / "focus" / "spec-queries.json").write_text(json.dumps(examples, indent=1))
(SITE / "practice-queries.json").write_text(json.dumps(practice, indent=1))
examples = practice + examples
ok_sample = sum(e["sample"]["ok"] for e in examples)
ok_ex = sum(e["examples"]["ok"] for e in examples)
nonempty_sample = sum(e["sample"].get("rows", 0) > 0 for e in examples)
nonempty_ex = sum(e["examples"].get("rows", 0) > 0 for e in examples)
print(f"{len(examples)} queries | run on sample: {ok_sample} ({nonempty_sample} return rows) | "
      f"run on 1.5 examples: {ok_ex} ({nonempty_ex} return rows)")
for e in examples:
    if not (e["sample"]["ok"] or e["examples"]["ok"]):
        print("FAIL", e["id"], "|", e["title"], "|", e["examples"].get("error"))
