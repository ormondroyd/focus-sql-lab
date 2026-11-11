"""Extract the FOCUS data model from the specification: datasets, columns and documented joins.

Usage: python -I extract_model.py <FOCUS_Spec clone> <site dir>
Writes <site dir>/focus/model.json.

Datasets and columns are read from the spec's Markdown. The relationships below are written out by hand from
each dataset's "Relationships" section (and two Invoice Detail column definitions); the source of each is recorded.
"""

import json
import pathlib
import re
import subprocess
import sys

SPEC = pathlib.Path(sys.argv[1])
SITE = pathlib.Path(sys.argv[2])
DS = SPEC / "specification/datasets"

DATASETS = [  # model id, spec folder (the lab's table has the same name as the model id)
    ("CostAndUsage", "cost_and_usage"),
    ("SkuPrice", "sku_price"),
    ("InvoiceDetail", "invoice_detail"),
    ("ContractCommitment", "contract_commitment"),
    ("BillingPeriod", "billing_period"),
]


def clean(md):
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)
    md = md.replace("**", "")
    md = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"\1", md)
    md = md.replace("\\<", "<").replace("\\[", "[").replace("\\*", "*").replace("`", "")
    return md.strip()


def section(text, name):
    m = re.search(rf"^## {re.escape(name)}\b[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def prose(md):
    """Paragraphs and bullets of a Markdown section, without tables."""
    blocks = []
    for block in re.split(r"\n\s*\n", md):
        lines = [re.sub(r"^\s*>\s?", "", l) for l in block.split("\n") if not l.lstrip().startswith("|")]
        text = clean("\n".join(lines))
        if text:
            blocks.append(text)
    return blocks


def constraints(text):
    out = {}
    for k, v in re.findall(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$", section(text, "Content Constraints"), re.M):
        if k == "Constraint" or set(k) <= set("-: "):
            continue
        out[k] = clean(v)
    return out


def requirements(text):
    """The Requirements section, line by line and exactly as written: lead sentences, bullets with their depth,
    sub-headings and tables. Each keeps its line number in the file, so the history can say which pull request last
    changed it."""
    out, inside, table = [], False, None
    for i, line in enumerate(text.split("\n"), 1):
        if re.match(r"^## Requirements", line):
            inside = True
            continue
        if inside and re.match(r"^#{1,2} ", line):
            break
        if not inside:
            continue
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if all(set(c) <= set(":- ") for c in cells):
                continue  # the row under a table's header
            if table is None:
                table = {"table": [], "line": i}
                out.append(table)
            table["table"].append(cells)
            continue
        table = None
        if not line.strip():
            continue
        m = re.match(r"^(\s*)[*-] (.*)$", line)
        if m:
            out.append({"depth": len(m.group(1).expandtabs(2)) // 2, "md": m.group(2).strip(), "line": i})
        elif line.startswith("###"):
            out.append({"heading": line.lstrip("# ").strip(), "line": i})
        else:
            out.append({"depth": -1, "md": line.strip(), "line": i})
    return out


def allowed_values(text):
    """The Allowed Values table, any width: header row first, then one row per value."""
    rows = [[clean(c.strip()) for c in line.strip().strip("|").split("|")]
            for line in section(text, "Allowed Values").split("\n") if line.lstrip().startswith("|")]
    return [r for r in rows if not all(set(c) <= set(":- ") for c in r)]


def rel_path(p):
    return str(p.relative_to(SPEC))


datasets = []
for ds_id, folder in DATASETS:
    path = DS / folder / "dataset.md"
    text = path.read_text()
    order = list(dict.fromkeys(re.findall(r"\(#datamodel\.[a-z]+\.([a-z0-9]+)\)", section(text, "Columns"))))
    columns = []
    for col in order:
        cpath = DS / folder / "columns" / f"{col}.md"
        if not cpath.exists():
            continue
        ct = cpath.read_text()
        c = constraints(ct)
        columns.append({
            "id": clean(section(ct, "Column ID")),
            "name": clean(section(ct, "Display Name")),
            "description": clean(section(ct, "Description")),
            "column_type": c.get("Column type"),
            "feature_level": c.get("Feature level"),
            "allows_nulls": c.get("Allows nulls"),
            "data_type": c.get("Data type"),
            "value_format": c.get("Value format"),
            "conditions": c.get("Operating model conditions"),
            "introduced": clean(section(ct, "Version Introduced")),
            "source": rel_path(cpath),
            "requirements": requirements(ct),
            "allowed_values": allowed_values(ct),
        })
    datasets.append({
        "id": ds_id,
        "name": clean(section(text, "Display Name")) or clean(text.split("\n", 1)[0].lstrip("# ")),
        "description": clean(section(text, "Description")),
        "relationships_text": prose(section(text, "Relationships")),
        "preview": "**Preview:**" in text,
        "introduced": clean(section(text, "Version Introduced")),
        "source": rel_path(path),
        "requirements": requirements(text),
        "columns": columns,
    })

# Attributes: the shared rule sets that dataset and column requirements point to, such as StringHandling.
attributes = []
for path in sorted((SPEC / "specification/attributes").glob("*.md")):
    if path.name == "attributes_overview.md":
        continue
    text = path.read_text()
    name = clean(section(text, "Attribute Name"))
    attributes.append({
        "id": clean(section(text, "Attribute ID")),
        "name": name,
        "anchor": name.lower().replace(" ", ""),  # how the spec links to it, e.g. #attributes.date/timeformat
        "description": clean(section(text, "Description")),
        "introduced": clean(section(text, "Version Introduced")),
        "source": rel_path(path),
        "requirements": requirements(text),
        "used_by": [],
    })
by_anchor = {a["anchor"]: a for a in attributes}

# Operating model conditions: what makes a Conditional column required (e.g. "Includes Payable Invoices").
conditions = []
for path in sorted((SPEC / "specification/operating_model_conditions").glob("*.md")):
    text = path.read_text()
    first = text.split("\n", 1)[1].strip().split("\n\n")[0]
    name = clean(text.split("\n", 1)[0].lstrip("# "))
    conditions.append({"id": clean(section(text, "Operating Model Condition ID")), "name": name,
                       "anchor": name.lower().replace(" ", ""),  # how the spec links to it
                       "description": clean(first), "introduced": clean(section(text, "Version Introduced")),
                       "source": rel_path(path), "requirements": requirements(text), "used_by": []})
by_cond = {c["anchor"]: c for c in conditions}
for c in conditions:
    for d in datasets:
        for col in d["columns"]:
            if col["conditions"] and c["name"] in col["conditions"]:
                c["used_by"].append([d["id"], col["id"]])
for d in datasets:  # requirements that name a condition, e.g. "When IncludesUnitPricing evaluates to true"
    for owner, reqs in [(None, d["requirements"])] + [(col["id"], col["requirements"]) for col in d["columns"]]:
        for anchor in dict.fromkeys(re.findall(r"\(#operatingmodelconditions\.([^)]+)\)", " ".join(r.get("md", "") for r in reqs))):
            if anchor in by_cond and [d["id"], owner] not in by_cond[anchor]["used_by"]:
                by_cond[anchor]["used_by"].append([d["id"], owner])

# Supporting material: appendix topics, metadata areas and JSON schemas, each a page or a folder of pages.
SPECDIR = SPEC / "specification"
TOPICS = [  # kind, path (file or folder) relative to specification/, main page (for folders)
    *[("appendix", f, m) for f, m in [
        ("appendix/ai_model_billing_examples", "ai_model_billing_examples.md"), ("appendix/ai_model_identity_examples.md", None),
        ("appendix/ai_prompt_caching_examples.md", None), ("appendix/commitment_discounts", "commitment_discounts.md"),
        ("appendix/commitment_program_eligibility_details_examples.md", None),
        ("appendix/contract_commitments", "contract_commitments.md"),
        ("appendix/correction_handling_examples", "correction_handling_examples_overview.md"),
        ("appendix/discount_handling.md", None),
        ("appendix/examples/commitment_discount_flexibility_examples", "commitment_discount_flexibility_examples_overview.md"),
        ("appendix/grouping_constructs_for_resources_and_or_services.md", None),
        ("appendix/invoice_and_billing_period_handling.md", None), ("appendix/invoice_detail", "invoice_detail.md"),
        ("appendix/json_object_examples", "json_object_examples_overview.md"),
        ("appendix/metadata_examples", "metadata_examples_overview.md"),
        ("appendix/participating_entity_identification.md", None), ("appendix/requester_attribution.md", None),
        ("appendix/rounding_variance_tolerance.md", None), ("appendix/saas_examples", "saas_examples_overview.md"),
        ("appendix/sku_price_examples", "sku_price_examples_overview.md"), ("appendix/split_cost_allocation_examples.md", None),
        ("appendix/split_cost_allocation_field_mapping.md", None)]],
    *[("metadata", f, m) for f, m in [
        ("metadata/metadata_overview.md", None), ("metadata/data_generator", "data_generator_overview.md"),
        ("metadata/dataset_instance", "dataset_instance_overview.md"), ("metadata/recency", "recency_overview.md"),
        ("metadata/schema", "schema_overview.md")]],
    *[("schema", str(p.relative_to(SPECDIR)), None) for p in sorted((SPECDIR / "schemas").rglob("*.json"))],
]
norm = lambda t: re.sub(r"\s+", "", t.lower())
topics = []
for kind, rel, main in TOPICS:
    path = SPECDIR / rel
    files = sorted(path.rglob("*.md")) if path.is_dir() else [path]
    if path.is_dir() and main is None:
        main = files[0].name
    primary = path / main if path.is_dir() else path
    text = primary.read_text()
    tid = re.sub(r"[^a-z0-9]+", "-", rel.rsplit(".", 1)[0].split("/", 1)[1].lower()).strip("-")
    if kind == "schema":
        name = json.loads(text).get("title") or primary.stem
        description = json.loads(text).get("description", "")
    else:
        name = clean(text.split("\n", 1)[0].lstrip("# "))
        description = clean(section(text, "Description") or text.split("\n", 1)[1].strip().split("\n\n")[0])
    headings = {norm(clean(h)) for f in files for h in re.findall(r"^#{1,4} +(.+)$", f.read_text(), re.M)}
    topics.append({"id": tid, "kind": kind, "name": name, "description": description, "source": rel_path(primary),
                   "files": [rel_path(f) for f in files], "pages": [clean(f.read_text().split("\n", 1)[0].lstrip("# "))
                   for f in files] if len(files) > 1 else [], "requirements": requirements(text) if kind == "metadata" else [],
                   "json": text if kind == "schema" else None, "headings": sorted(headings), "referenced_by": []})

# Resolve every link the spec makes to this material, e.g. #appendix.examples:participatingentityidentification.
ref_anchor = {}
by_id = {t["id"]: t for t in topics}
everything = " ".join((SPECDIR / f).read_text() for f in [] ) + " ".join(
    p.read_text() for p in list((SPECDIR / "datasets").rglob("*.md")) + list((SPECDIR / "attributes").glob("*.md"))
    + list((SPECDIR / "operating_model_conditions").glob("*.md")) + list((SPECDIR / "metadata").rglob("*.md"))
    + list((SPECDIR / "appendix").rglob("*.md")))
for target in sorted(set(re.findall(r"\]\(#((?:appendix|metadata|schemas)[^)]*)\)", everything))):
    if target.startswith("schemas."):
        hit = next((t for t in topics if t["kind"] == "schema" and t["source"].endswith(target.rsplit(".", 1)[1] + ".json")), None)
    elif target.startswith("metadata"):
        parts = target.split(".")
        want = parts[1] if len(parts) > 1 else "metadata"
        hit = next((t for t in topics if t["kind"] == "metadata" and t["source"].split("/")[2].replace("_", "").startswith(want)), None)
    else:
        segs = [x for x in re.split(r"[.:]", target)[1:] if x not in ("examples", "example")]
        # The spec's link names are headings or folder names run together, often shortened: "aimodelbilling" for
        # "AI Model Billing Examples". Prefer an exact match, then a prefix match, segment by segment.
        def keys(t):
            return set(t["headings"]) | {re.sub(r"[_\s]", "", pathlib.Path(t["source"]).parent.name if len(t["files"]) > 1
                                           else pathlib.Path(t["source"]).stem)}
        def folder(t):
            return re.sub(r"[_\s]", "", pathlib.Path(t["source"]).parent.name if len(t["files"]) > 1 else pathlib.Path(t["source"]).stem)
        apx = [t for t in topics if t["kind"] == "appendix"]
        hit = None
        for seg in segs:
            hit = (next((t for t in apx if seg in keys(t)), None)                   # exact heading or folder name
                   or next((t for t in apx if folder(t).startswith(seg)), None)     # shortened folder name
                   or next((t for t in apx if any(k.startswith(seg) for k in t["headings"])), None))
            if hit:
                break
        # One link names the page by its title, which the folder and headings don't share.
        hit = hit or {"appendix.examples:datagenerator-calculatedsplitcostallocation": by_id.get("split-cost-allocation-examples")}.get(target)
    if hit:
        ref_anchor[target] = hit["id"]
unresolved = sorted(set(re.findall(r"\]\(#((?:appendix|metadata|schemas)[^)]*)\)", everything)) - set(ref_anchor))
by_topic = {t["id"]: t for t in topics}
for d in datasets:  # every dataset and column page that links to the topic, anywhere on the page
    for owner, src in [(None, d["source"])] + [(c["id"], c["source"]) for c in d["columns"]]:
        for target in re.findall(r"\(#((?:appendix|metadata|schemas)[^)]*)\)", (SPEC / src).read_text()):
            if target in ref_anchor and [d["id"], owner] not in by_topic[ref_anchor[target]]["referenced_by"]:
                by_topic[ref_anchor[target]]["referenced_by"].append([d["id"], owner])
for t in topics:
    del t["headings"]
print(f"{len(topics)} supporting topics; {len(ref_anchor)} link targets resolved; unresolved: {unresolved}")

# Glossary: the defined terms that requirements link to, e.g. #glossary:covered-charge.
glossary = {}
gtext = (SPEC / "specification/glossary.md").read_text()
for m in re.finditer(r'<a name="glossary:([^"]+)"><b>([^<]+)</b></a>\s*\n(.*?)(?=\n<a name="glossary:|\Z)', gtext, re.S):
    glossary[m.group(1)] = {"term": m.group(2).strip(), "definition": clean(m.group(3).strip())}
for d in datasets:
    for owner, reqs in [(None, d["requirements"])] + [(c["id"], c["requirements"]) for c in d["columns"]]:
        for anchor in dict.fromkeys(re.findall(r"\(#attributes\.([^)]+)\)", " ".join(r.get("md", "") for r in reqs))):
            if anchor in by_anchor:
                by_anchor[anchor]["used_by"].append([d["id"], owner])


def stats_sql(a, b, keys):
    """Coverage of a join in the loaded data: rows carrying the key, and rows that find a match."""
    keys = [k for k in keys if len(k) < 3]  # optional keys are left out of the match
    fsel = ", ".join(f'"{x}" AS k{i}' for i, (x, _) in enumerate(keys))
    tsel = ", ".join(f'"{y}" AS k{i}' for i, (_, y) in enumerate(keys))
    on = " AND ".join(f"t.k{i} = f.k{i}" for i in range(len(keys)))
    notnull = " AND ".join(f"f.k{i} IS NOT NULL" for i in range(len(keys)))
    tup = "concat_ws('|', " + ", ".join(f"f.k{i}" for i in range(len(keys))) + ")"
    return (f"WITH f AS (SELECT {fsel} FROM {a}), t AS (SELECT DISTINCT {tsel} FROM {b})\n"
            f"SELECT count(*) AS rows_total,\n"
            f"  count(*) FILTER (WHERE {notnull}) AS rows_with_key,\n"
            f"  count(*) FILTER (WHERE t.k0 IS NOT NULL) AS rows_matched,\n"
            f"  count(DISTINCT CASE WHEN {notnull} THEN {tup} END) AS keys_distinct,\n"
            f"  count(DISTINCT CASE WHEN t.k0 IS NOT NULL THEN {tup} END) AS keys_matched\n"
            f"FROM f LEFT JOIN t ON {on}")


CC_STATS = """WITH c AS (SELECT row_number() OVER () AS r, ContractApplied FROM CostAndUsage),
  e AS (SELECT c.r, x ->> '$.ContractCommitmentId' AS k0
        FROM c CROSS JOIN unnest(CAST(json_extract(c.ContractApplied, '$.Elements') AS JSON[])) AS u(x)),
  t AS (SELECT DISTINCT ContractCommitmentId AS k0 FROM ContractCommitment)
SELECT (SELECT count(*) FROM c) AS rows_total,
  (SELECT count(*) FROM c WHERE ContractApplied IS NOT NULL) AS rows_with_key,
  (SELECT count(DISTINCT e.r) FROM e JOIN t USING (k0)) AS rows_matched,
  (SELECT count(DISTINCT k0) FROM e) AS keys_distinct,
  (SELECT count(DISTINCT k0) FROM e JOIN t USING (k0)) AS keys_matched"""

S = "specification/datasets/"
RELS = [
    {"id": "cau-sku", "name": "Charge → SKU price", "a": "CostAndUsage", "b": "SkuPrice",
     "keys": [["ServiceProviderName", "ServiceProviderName"], ["SkuPriceId", "SkuPriceId"]],
     "also": ["ChargePeriodStart is on or after SkuPriceEffectiveStart and before SkuPriceEffectiveEnd (null = open-ended)",
              "ContractId matches ContractApplied.Elements[*].ContractId, or is null for a public list price",
              "PricingCurrency matches the charge's PricingCurrency, or BillingCurrency",
              "UnitPriceType is filtered to one value, e.g. 'List'"],
     "cardinality": "Many to many: one SKU Price ID has a price record per effective period, contract, pricing currency and unit price type.",
     "source": S + "sku_price/dataset.md",
     "join_sql": """-- Resolve the public list price for each charge, using the spec's matching criteria
SELECT c.ChargePeriodStart, c.ServiceProviderName, c.SkuPriceId,
       c.ListUnitPrice, s.UnitPrice AS CatalogListPrice, s.PricingCurrency,
       s.SkuPriceEffectiveStart, s.SkuPriceEffectiveEnd
FROM CostAndUsage c
JOIN SkuPrice s
  ON s.ServiceProviderName = c.ServiceProviderName
 AND s.SkuPriceId = c.SkuPriceId
 AND s.ContractId IS NULL
 AND s.UnitPriceType = 'List'
 AND s.PricingCurrency = COALESCE(c.PricingCurrency, c.BillingCurrency)
 AND (s.SkuPriceEffectiveStart IS NULL OR c.ChargePeriodStart >= s.SkuPriceEffectiveStart)
 AND (s.SkuPriceEffectiveEnd IS NULL OR c.ChargePeriodStart < s.SkuPriceEffectiveEnd)
LIMIT 200;"""},
    {"id": "cau-cc", "name": "Charge → contract commitment", "a": "CostAndUsage", "b": "ContractCommitment",
     "keys": [["ContractApplied", "ContractCommitmentId"]],
     "also": ["The key is inside a JSON array: ContractApplied.Elements[*].ContractCommitmentId"],
     "cardinality": "Many to many: a charge can apply several commitments, and a commitment applies to many charges.",
     "source": S + "contract_commitment/dataset.md", "stats_sql": CC_STATS,
     "join_sql": """-- Unpack ContractApplied and join each element to its contract commitment
SELECT c.ChargePeriodStart, c.ChargeCategory, c.EffectiveCost,
       x ->> '$.ContractCommitmentId' AS ContractCommitmentId,
       x ->> '$.ContractCommitmentAppliedCost' AS AppliedCost,
       cc.ContractCommitmentCategory, cc.ContractCommitmentType, cc.ContractCommitmentCost
FROM CostAndUsage c
CROSS JOIN unnest(CAST(json_extract(c.ContractApplied, '$.Elements') AS JSON[])) AS u(x)
JOIN ContractCommitment cc ON cc.ContractCommitmentId = x ->> '$.ContractCommitmentId'
LIMIT 200;"""},
    {"id": "cau-inv", "name": "Charge → invoice detail", "a": "CostAndUsage", "b": "InvoiceDetail",
     "keys": [["InvoiceIssuerName", "InvoiceIssuerName"], ["InvoiceId", "InvoiceId"], ["InvoiceDetailId", "InvoiceDetailId", "optional"]],
     "also": ["Invoice Detail ID is optional, for record-level matching",
              "One or both datasets need to be aggregated before comparing",
              "Some data generators only fill Invoice ID in Cost and Usage after the billing period closes"],
     "cardinality": "Many to many at invoice level; add Invoice Detail ID to match individual invoice records.",
     "source": S + "invoice_detail/dataset.md",
     "join_sql": """-- Compare each invoice's total with the Cost and Usage charges that carry its ID
WITH cu AS (SELECT InvoiceIssuerName, InvoiceId, sum(BilledCost) AS CostAndUsageBilled
            FROM CostAndUsage WHERE InvoiceId IS NOT NULL GROUP BY ALL),
     inv AS (SELECT InvoiceIssuerName, InvoiceId, sum(BilledCost) AS InvoiceBilled
             FROM InvoiceDetail GROUP BY ALL)
SELECT InvoiceIssuerName, InvoiceId, InvoiceBilled, CostAndUsageBilled,
       round(InvoiceBilled - CostAndUsageBilled, 2) AS Difference
FROM inv FULL OUTER JOIN cu USING (InvoiceIssuerName, InvoiceId)
ORDER BY 1, 2;"""},
    {"id": "cau-bp", "name": "Charge → billing period", "a": "CostAndUsage", "b": "BillingPeriod",
     "keys": [["InvoiceIssuerName", "InvoiceIssuerName"], ["BillingPeriodStart", "BillingPeriodStart"]],
     "also": [], "cardinality": "Many to one: each charge belongs to one billing period of its invoice issuer.",
     "source": S + "billing_period/dataset.md",
     "join_sql": """-- Billed cost by billing period and its status (open or closed)
SELECT c.InvoiceIssuerName, c.BillingPeriodStart, bp.BillingPeriodStatus,
       round(sum(c.BilledCost), 2) AS BilledCost
FROM CostAndUsage c
JOIN BillingPeriod bp USING (InvoiceIssuerName, BillingPeriodStart)
GROUP BY ALL ORDER BY 1, 2;"""},
    {"id": "inv-bp", "name": "Invoice detail → billing period", "a": "InvoiceDetail", "b": "BillingPeriod",
     "keys": [["InvoiceIssuerName", "InvoiceIssuerName"], ["BillingPeriodStart", "BillingPeriodStart"]],
     "also": [], "cardinality": "Many to one: each invoice record belongs to one billing period of its invoice issuer.",
     "source": S + "billing_period/dataset.md",
     "join_sql": """-- Invoiced totals by billing period and its status
SELECT i.InvoiceIssuerName, i.BillingPeriodStart, bp.BillingPeriodStatus,
       round(sum(i.BilledCost), 2) AS InvoiceBilled
FROM InvoiceDetail i
JOIN BillingPeriod bp USING (InvoiceIssuerName, BillingPeriodStart)
GROUP BY ALL ORDER BY 1, 2;"""},
    {"id": "sku-cc", "name": "SKU price → contract commitment", "a": "SkuPrice", "b": "ContractCommitment",
     "keys": [["ContractId", "ContractId"]],
     "also": ["Optional: relates a contracted price to its overarching contract"],
     "cardinality": "Many to many: a contract carries many prices and may have several commitments.",
     "source": S + "sku_price/dataset.md",
     "join_sql": """-- Contracted prices alongside the commitments of the same contract
SELECT s.ContractId, s.SkuId, s.UnitPriceType, s.UnitPrice, s.PricingUnit,
       cc.ContractCommitmentId, cc.ContractCommitmentCategory, cc.ContractCommitmentType
FROM SkuPrice s
JOIN ContractCommitment cc ON cc.ContractId = s.ContractId
LIMIT 200;"""},
    {"id": "inv-pay", "name": "Invoice record → payment currency record", "a": "InvoiceDetail", "b": "InvoiceDetail",
     "keys": [["PaymentCurrencyInvoiceDetailId", "InvoiceDetailId"]],
     "also": [], "cardinality": "Many to one: records point to the record that carries their Payment Currency Billed Cost.",
     "source": S + "invoice_detail/columns/paymentcurrencyinvoicedetailid.md",
     "join_sql": """-- Each invoice record with the record holding its payment-currency amount
SELECT d.InvoiceId, d.InvoiceDetailId, d.BilledCost, d.BillingCurrency,
       p.InvoiceDetailId AS PaymentRecord, p.PaymentCurrency, p.PaymentCurrencyBilledCost
FROM InvoiceDetail d
JOIN InvoiceDetail p ON p.InvoiceDetailId = d.PaymentCurrencyInvoiceDetailId
ORDER BY 1, 2;"""},
    {"id": "inv-ref", "name": "Invoice → invoice it adjusts", "a": "InvoiceDetail", "b": "InvoiceDetail",
     "keys": [["ReferenceInvoiceId", "InvoiceId"]],
     "also": ["Matches the invoice's own ID when it doesn't adjust another invoice"],
     "cardinality": "Many to one: an adjusting invoice (e.g. a credit note) points to the original invoice.",
     "source": S + "invoice_detail/columns/referenceinvoiceid.md",
     "join_sql": """-- Invoices that adjust an earlier invoice
SELECT DISTINCT d.InvoiceId, d.ReferenceInvoiceId, o.InvoiceIssueDate AS OriginalIssued
FROM InvoiceDetail d
JOIN InvoiceDetail o ON o.InvoiceId = d.ReferenceInvoiceId
WHERE d.ReferenceInvoiceId <> d.InvoiceId;"""},
]
for r in RELS:
    r.setdefault("stats_sql", stats_sql(r["a"], r["b"], r["keys"]))

commit = subprocess.run(["git", "-C", str(SPEC), "log", "-1", "--format=%h %cs"],
                        capture_output=True, text=True).stdout.split()
model = {
    "spec": {"repo": "https://github.com/FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec",
             "ref": commit[0] if commit else None, "date": commit[1] if len(commit) > 1 else None},
    "datasets": datasets,
    "attributes": attributes,
    "conditions": conditions,
    "topics": topics,
    "ref_anchor": ref_anchor,
    "glossary": glossary,
    "relationships": RELS,
}
out = SITE / "focus" / "model.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(model, indent=1))
print(f"wrote {out}: {len(datasets)} datasets, {sum(len(d['columns']) for d in datasets)} columns, "
      f"{len(RELS)} relationships (spec {model['spec']['ref']})")
for d in datasets:
    print(f"  {d['id']}: {len(d['columns'])} columns, preview={d['preview']}, "
          f"relationship paragraphs={len(d['relationships_text'])}")
