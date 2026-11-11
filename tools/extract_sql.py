"""Copy the FOCUS spec's example SQL exactly as published, suggest a value for each ? input, and test every query.
Also tests the lab's own practice queries (tools/practice.json).

Usage: python -I extract_sql.py <FOCUS_Spec clone> <site dir>
Reads  <site dir>/focus/data/ (Parquet and manifest), <site dir>/focus/model.json and <site dir>/lab-setup.sql
Writes <site dir>/focus/spec-queries.json   (the specification's queries, verbatim: FOCUS-derived)
       <site dir>/practice-queries.json     (the lab's own practice queries, with test results)

Each spec query is stored exactly as the specification publishes it. Its ? inputs are left in place: the spec uses ?
to mark values the reader supplies. The lab suggests a typed value for each one (text, number or timestamp) from the
data. When a query runs, each ? is replaced by its value as a typed SQL literal, the way a database client binds a
parameter. The page does the same thing in JavaScript (bindInputs in index.html).
"""

import datetime
import json
import pathlib
import re
import sys

import duckdb

SPEC = pathlib.Path(sys.argv[1])
SITE = pathlib.Path(sys.argv[2])
DATA = SITE / "focus" / "data"

SOURCES = sorted((SPEC / "specification/supported_features").glob("*.md"))
SOURCES += [SPEC / "supporting_content/appendix/version_migration_guidance.md"]

START, END = "2000-01-01 00:00:00", "2100-01-01 00:00:00"


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
manifest = json.loads((DATA / "manifest.json").read_text())
for t, m in manifest["tables"].items():
    con.execute(f"CREATE VIEW {t} AS SELECT * FROM '{DATA / m['file']}'")
# Each FOCUS dataset name is a view onto the chosen source's table, or onto an empty table with the spec's columns
# when the source doesn't have that dataset. The page does the same (setDataset in index.html).
SQL_TYPE = {"String": "VARCHAR", "Decimal": "DOUBLE", "Date/Time": "TIMESTAMP", "JSON": "VARCHAR"}
DATASETS = json.loads((SITE / "focus" / "model.json").read_text())["datasets"]
for d in DATASETS:
    cols = ", ".join(f'"{c["id"]}" {SQL_TYPE.get(c["data_type"], "VARCHAR")}' for c in d["columns"])
    con.execute(f'CREATE TABLE "empty_{d["id"]}" ({cols})')
SOURCES_DATA = manifest["sources"]


def set_source(src):
    for d in DATASETS:
        table = SOURCES_DATA[src]["tables"].get(d["id"], "empty_" + d["id"])
        con.execute(f'CREATE OR REPLACE VIEW "{d["id"]}" AS SELECT * FROM "{table}"')


set_source("examples")
con.execute("SELECT json_extract_string('{}', '$')")  # load DuckDB's JSON functions before the lab replaces json_value
con.execute((SITE / "lab-setup.sql").read_text())

POINT = "2026-03-01 00:00:00"  # inside the Aura Web price list's effective dates
CONTRACT = "auraweb:contract::ACCT-123456789012:agreements/ctr-7f3a91b2c4d5"
VM_LIST_PRICE = con.execute(
    "SELECT SkuPriceId FROM SkuPrice WHERE SkuId = 'AURAWEB-COMPUTE-VM-STD-8X32' AND UnitPriceType = 'List' "
    "AND SkuPriceEffectiveStart <= TIMESTAMP '2026-03-01' AND SkuPriceEffectiveEnd IS NULL ORDER BY 1 LIMIT 1"
).fetchone()[0]
# Queries whose inputs describe one priced item: values chosen to match the spec's Aura Web price list.
SUGGESTIONS = {
    "catalog_discovery_and_price_estimation-2": ["Aura Web", VM_LIST_PRICE, 720, POINT],
    "catalog_discovery_and_price_estimation-3": ["Aura Web", POINT, POINT, "ACCT-123456789012"],
    "rate_optimization_and_contract_evaluation-1": ["Aura Web", "Aura Web Compute", CONTRACT, POINT],
    "rate_optimization_and_contract_evaluation-2": ["Aura Web", "AURAWEB-STORAGE-OBJECT-STD", "us-east-1",
                                                    "GB-Months", "USD", 100000, POINT, CONTRACT],
    "rate_optimization_and_contract_evaluation-4": ["Aura Web", "AURAWEB-STORAGE-OBJECT-STD",
                                                    "Aura Web", "AURAWEB-COMPUTE-VM-STD-8X32",
                                                    "Aura Web", "AURAWEB-DATABASE-MANAGED-STD", POINT, POINT],
    "rate_optimization_and_contract_evaluation-7": ["Aura Web", CONTRACT, START, END],
}
ALIASES = {"ID": "InvoiceDetail", "SP": "SkuPrice", "CU": "CostAndUsage", "CC": "ContractCommitment"}
TABLES = ["SkuPrice", "InvoiceDetail", "ContractCommitment", "CostAndUsage"]


DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2}(\.\d+)?)?)?$")


def typed(v):
    """An input value with its type: {"value": ..., "type": "text" | "number" | "timestamp"}."""
    if isinstance(v, datetime.datetime):
        return {"value": v.isoformat(sep=" "), "type": "timestamp"}
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return {"value": v, "type": "number"}
    if v is None:
        return {"value": None, "type": "text"}
    v = str(v)
    return {"value": v, "type": "timestamp" if DATETIME.match(v) else "text"}


def placeholders(sql):
    """Positions of the ? inputs, skipping any ? inside strings, quoted names and comments."""
    out, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if c in "'\"":  # a string or quoted name; a doubled quote inside it is an escaped quote
            j = i + 1
            while j < n:
                if sql[j] == c and sql[j + 1:j + 2] == c:
                    j += 2
                elif sql[j] == c:
                    break
                else:
                    j += 1
            i = j + 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            if c == "?":
                out.append(i)
            i += 1
    return out


def literal(p):
    v, t = p["value"], p["type"]
    if v is None or v == "":
        return "NULL"
    if t == "number":
        return repr(float(v)) if not re.match(r"^-?\d+$", str(v)) else str(int(v))
    quoted = "'" + str(v).replace("'", "''") + "'"
    return f"TIMESTAMP {quoted}" if t == "timestamp" else quoted


def bind(sql, params):
    """Replace each ? with its typed value, as the page does when it runs a query."""
    out, last = [], 0
    for pos, p in zip(placeholders(sql), params):
        out += [sql[last:pos], literal(p)]
        last = pos + 1
    return "".join(out) + sql[last:]


def common_value(table, col):
    try:
        v = con.execute(f'SELECT "{col}" FROM {table} WHERE "{col}" IS NOT NULL '
                        f"GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 1").fetchone()
    except duckdb.Error:
        return None
    return None if v is None else v[0]


def suggest(sql, eid):
    """Suggest a typed value for each ? input, from what the query compares it with."""
    if eid in SUGGESTIONS:
        return [typed(v) for v in SUGGESTIONS[eid]]
    primary = next((t for t in TABLES if re.search(rf"\bFROM\s+{t}\b", sql)), "CostAndUsage")
    values = []
    for pos in placeholders(sql):
        before = sql[:pos]
        cm = re.search(r"(?:\b([A-Z]{2})\.)?([A-Za-z_][A-Za-z0-9_]*)\)?\s*(=|>=|<=|<>|>|<)\s*$", before)
        col, op = (cm.group(2), cm.group(3)) if cm else (None, None)
        table = ALIASES.get(cm.group(1), primary) if cm and cm.group(1) else primary
        if col and "Effective" in col:
            values.append(typed(POINT))
        elif col and re.search(r"(Start|End)$", col):
            values.append(typed(START if op in (">=", ">") else END))
        elif col:
            values.append(typed(common_value(table, col)))
        else:
            values.append(typed(None))
    return values


def run(sql, params, source):
    set_source(source)
    try:
        rows = con.execute(bind(sql, params)).fetchall()
        return {"ok": True, "rows": len(rows)}
    except duckdb.Error as e:
        return {"ok": False, "error": str(e).split("\n")[0][:300]}


NOTES = {
    "catalog_discovery_and_price_estimation-3": "Doesn't run in DuckDB as published. It tests whether a value is in a "
        "list with BigQuery's `value IN UNNEST(array)` form, which DuckDB doesn't support (DuckDB writes it "
        "list_contains(array, value)). The specification says this query may need small changes for a particular "
        "database engine.",
    "contract_commitments-3": "Doesn't run in DuckDB as published. In the GROUP BY, ContractCommitmentId matches both "
        "the SELECT alias built from JSON_VALUE(CA, ...) and the CC.ContractCommitmentId column. DuckDB takes the "
        "table column, so the JSON_VALUE expression in the SELECT list is left ungrouped. (Standard SQL doesn't "
        "allow SELECT aliases in GROUP BY at all.) Whether BigQuery accepts it hasn't been checked here.",
    "custom_columns-1": "Illustrative: x_CustomColumn stands for any provider-defined custom column, so this query "
        "fails in any database. Replace it with an x_ column that exists to run it.",
    "data_generator_calculated_split_cost_allocation-7": "Doesn't run in DuckDB as published. It uses "
        "JSON_TABLE(... COLUMNS (...)), standard SQL that DuckDB doesn't support. The specification's other JSON "
        "queries use BigQuery's JSON functions instead.",
}

examples = []
for md in SOURCES:
    for n, (feature, heading, intro, sql) in enumerate(blocks(md), 1):
        eid = f"{md.stem}-{n}"
        set_source("examples")  # inputs are suggested from the spec's worked examples
        params = suggest(sql, eid)
        assert len(params) == len(placeholders(sql)), eid
        example = {
            "id": eid,
            "feature": feature,
            "title": heading,
            "intro": intro,
            "source": str(md.relative_to(SPEC)),
            "sql": sql,
            "params": params,
            "results": {src: run(sql, params, src) for src in SOURCES_DATA},
        }
        if eid in NOTES:
            example["note"] = NOTES[eid]
        examples.append(example)

practice = json.loads((pathlib.Path(__file__).parent / "practice.json").read_text())
for p in practice:
    p.update({"feature": "Lab practice queries (DuckDB SQL, not from FOCUS)", "source": None, "params": [],
              "lab": True, "results": {src: run(p["sql"], [], src) for src in SOURCES_DATA}})
    print("practice", p["id"], p["results"])

(SITE / "focus" / "spec-queries.json").write_text(json.dumps(examples, indent=1))
(SITE / "practice-queries.json").write_text(json.dumps(practice, indent=1))
for label, group in (("spec", examples), ("practice", practice)):
    ok = sum(any(r["ok"] for r in e["results"].values()) for e in group)
    rows = sum(any(r.get("rows", 0) > 0 for r in e["results"].values()) for e in group)
    print(f"{label}: {len(group)} queries, {ok} run as published, {rows} return rows")
    for src in SOURCES_DATA:
        print(f"  {src}: {sum(e['results'][src].get('rows', 0) > 0 for e in group)} return rows")
for e in examples + practice:
    if not any(r["ok"] for r in e["results"].values()):
        print("FAIL", e["id"], "|", e["title"], "|", e["results"]["examples"].get("error"), "| note:", "note" in e)
