"""Extract the FOCUS spec's example SQL, convert BigQuery SQL to DuckDB, and test each query.

Usage: python -I extract_sql.py <FOCUS_Spec clone> <site/data dir> <output examples.json>
"""

import json
import pathlib
import re
import sys

import duckdb
import sqlglot

SPEC = pathlib.Path(sys.argv[1])
DATA = pathlib.Path(sys.argv[2])
OUT = pathlib.Path(sys.argv[3])

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
for t in ["cau_real", "cau_examples", "ContractCommitment", "InvoiceDetail", "SkuPrice", "CorrectionExamples"]:
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
        real, ex = run(duck, "cau_real"), run(duck, "cau_examples")
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
            "real": real,
            "examples": ex,
        })

OUT.write_text(json.dumps(examples, indent=1))
ok_real = sum(e["real"]["ok"] for e in examples)
ok_ex = sum(e["examples"]["ok"] for e in examples)
nonempty_real = sum(e["real"].get("rows", 0) > 0 for e in examples)
nonempty_ex = sum(e["examples"].get("rows", 0) > 0 for e in examples)
print(f"{len(examples)} queries | run on real: {ok_real} ({nonempty_real} return rows) | "
      f"run on 1.5 examples: {ok_ex} ({nonempty_ex} return rows)")
for e in examples:
    if not (e["real"]["ok"] or e["examples"]["ok"]):
        print("FAIL", e["id"], "|", e["title"], "|", e["examples"].get("error"))
