"""Build site/focus/ai-tokens.json: the AI tokens view.

How FOCUS records charges for AI model use, which are billed in tokens, and where the specification stops.
Specification text is copied exactly as published. If a sentence quoted below is no longer in the specification,
the script stops, so the view never quotes text the specification no longer says. Thread titles and status come
fresh from GitHub on each run. The headings and explanations under GAPS and HOW are the lab's own writing.

    GH_TOKEN=... python tools/extract_ai.py <FOCUS_Spec checkout> <site dir>
"""
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.request

SPEC, SITE = pathlib.Path(sys.argv[1]) / "specification", pathlib.Path(sys.argv[2])
REPO = "FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec"
FEATURE = "supported_features/ai_model_billing.md"
SKUPD = "datasets/cost_and_usage/columns/skupricedetails.md"


def read(rel):
    return (SPEC / rel).read_text()


def section(md, heading):
    """The text under a ## heading, up to the next ## heading."""
    m = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", md, re.M | re.S)
    assert m, f"no '## {heading}' section"
    return m.group(1).strip()


def bullets(text):
    return [l[2:].strip() for l in text.splitlines() if l.startswith("* ")]


def quote(md, start, source):
    """The whole sentence or requirement that begins with `start`, exactly as published."""
    i = md.find(start)
    assert i >= 0, f"quoted text no longer in {source}: {start!r}"
    end = md.find("\n", i)
    line = md[i:end if end > 0 else None]
    m = re.match(r".*?\.(?=\s|$)", line)
    return {"text": m.group(0) if m else line, "source": source}


feature_md = read(FEATURE)
skupd_md = read(SKUPD)
glossary_md = read("glossary.md")

# The FOCUS-defined SkuPriceDetails properties that describe AI models and tokens.
props = []
for line in section(skupd_md, "FOCUS-Defined Properties").splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) == 4 and re.match(r"(Model|Token)[A-Z]", cells[0]):
        props.append(dict(zip(["key", "description", "type", "values"], [re.sub(r"<sup>\d+</sup>", "", c).strip() for c in cells])))
assert {"ModelId", "TokenDirection", "TokenCacheAction"} <= {p["key"] for p in props}, "AI properties missing"
note = re.search(r"^> 4\. (.*)$", skupd_md, re.M)
assert note and "TokenDirection" in note.group(1), "SkuPriceDetails note 4 has moved"

model_id = next(p for p in props if p["key"] == "ModelId")

HOW = [
    "A token charge is an ordinary Cost and Usage row. ServiceCategory is \"AI and Machine Learning\", ConsumedUnit "
    "is \"Tokens\" and ConsumedQuantity counts them. PricingQuantity and PricingUnit say how they were priced, which "
    "can be in blocks, such as per million tokens.",
    "Which model, and which kind of token, are recorded inside one JSON column, SkuPriceDetails, as FOCUS-defined "
    "properties. ModelDeveloper, ModelFamily, ModelId and ModelVersion describe the model. TokenDirection (input or "
    "output) and TokenCacheAction (uncached, cache read, cache write) describe the tokens. All six are new in the 1.5 "
    "candidate.",
    "Who made the request can be recorded in three columns, also new in 1.5: PrincipalId, CredentialId and "
    "RequesterDetails, for example the service account or API key behind the calls.",
    "Everything else, such as cost, currency, period and provider, uses the same columns as any other charge.",
]

# How the current model came about, in the order the threads were opened.
DECIDED = [1941, 2018, 2099, 2442, 2550, 2605, 2606, 2617]

GAPS = [
    {"id": "optional", "title": "The token details are optional",
     "text": "SkuPriceDetails is a conditional column that may be empty even when a price is identified, and the "
             "model and token properties are recommendations (SHOULD), not requirements. A provider can conform "
             "without them, so comparing token costs across providers depends on each one choosing to fill them in.",
     "quotes": [quote(skupd_md, "SkuPriceDetails MAY be null when SkuPriceId is not null", SKUPD),
                quote(skupd_md, "SkuPriceDetails SHOULD include TokenDirection when", SKUPD)],
     "threads": []},
    {"id": "json", "title": "They sit inside a JSON column",
     "text": "The working group chose properties inside SkuPriceDetails over new columns (#2018, #2442), and newer "
             "proposals follow the same pattern, such as region scope (#2613). That keeps the column list stable, but "
             "every token query has to unpack JSON. The specification's queries use BigQuery's JSON_VALUE, which "
             "other databases write differently: the lab runs them in DuckDB through a small json_value macro.",
     "quotes": [quote(feature_md, "Similar JSON functions are widely available", FEATURE)],
     "threads": [2613, 2850]},
    {"id": "compare", "title": "Models and tokens don't line up across providers",
     "text": "The same model can carry a different ModelId from each seller, and a token is not a fixed amount of "
             "content. So a cost per million tokens compares prices, not work done, and comparing one model across "
             "providers needs ModelDeveloper, ModelFamily and ModelVersion filled in as well.",
     "quotes": [{"text": f"ModelId: {model_id['description']}.", "source": SKUPD},
                quote(glossary_md, "The amount of content a single token represents", "glossary.md")],
     "threads": []},
    {"id": "dimensions", "title": "Pricing dimensions not covered yet",
     "text": "The specification names dimensions that the token properties deliberately leave out, and each has an "
             "open request. Others have been raised since: processing tiers such as batch or priority, provisioned "
             "throughput, regional prices and finer AI service subcategories. A query for what caching saves was "
             "taken out until the SKU Price dataset can supply the uncached price (#2702).",
     "quotes": [quote(note.group(1), "Dimensions that qualify a charge", SKUPD)],
     "threads": [2489, 2805, 2487, 2488, 2521, 2817, 2437, 2371, 2414, 1943, 2702]},
    {"id": "data", "title": "No public data with token charges yet",
     "text": "Only the specification's worked examples contain token rows. The token queries return nothing on the "
             "accepted 1.0 sample or on the samples proposed for 1.3 and 1.4, so no public FOCUS sample data yet "
             "shows token billing.",
     "quotes": [], "threads": []},
    {"id": "beyond", "title": "Nothing yet on energy, utilisation or results",
     "text": "FOCUS records what was charged. The specification has no column or property for energy use or "
             "emissions, for how busy the resources behind a charge were, or for what the tokens produced. The request "
             "that added model identity (#2018) left operational telemetry out of scope. Open requests would "
             "cover parts of this: sustainability measures, a companion utilisation dataset (which absorbed a request "
             "for AI and GPU utilisation), a mapping from OpenTelemetry, and costs for work that never reached a "
             "billed SKU.",
     "quotes": [{"text": "Those belong in observability tooling, not cost and usage data.", "source": "#2018", "thread": True,
                 "context": "The model identity request's own scope, on latency, CPU use and sampling settings"}],
     "threads": [972, 2654, 1022, 2728, 2699]},
]

# The "no public data" gap holds only while no non-example source returns token rows.
TOKEN_QUERIES = ["ai_model_billing-1", "ai_model_billing-2", "resource_usage-2", "resource_usage-3"]
queries = {q["id"]: q for q in json.loads((SITE / "focus" / "spec-queries.json").read_text())}
outside = [(i, k) for i in TOKEN_QUERIES for k, r in queries[i]["results"].items() if k != "examples" and r.get("rows")]
if outside:
    GAPS = [g for g in GAPS if g["id"] != "data"]
    print("token rows found outside the worked examples:", outside)


def gh(path):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}",
                                 headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


threads = {}
for n in sorted(set(DECIDED) | {n for g in GAPS for n in g["threads"]}):
    i = gh(f"issues/{n}")
    pr = i.get("pull_request")
    threads[n] = {"n": n, "title": i["title"], "url": i["html_url"], "kind": "pr" if pr else "issue",
                  "state": "merged" if pr and pr.get("merged_at") else i["state"],
                  "reason": None if pr else i.get("state_reason"),
                  "opened": i["created_at"][:10], "closed": (i["closed_at"] or "")[:10] or None,
                  "comments": i["comments"]}
DECIDED.sort(key=lambda n: threads[n]["opened"])

out = {
    "spec": json.loads((SITE / "focus" / "model.json").read_text())["spec"],
    "checked": datetime.date.today().isoformat(),
    "how": HOW,
    "feature": {"source": FEATURE, "description": section(feature_md, "Description"),
                "dependent": bullets(section(feature_md, "Directly Dependent Columns")),
                "supporting": bullets(section(feature_md, "Supporting Columns"))},
    "requester": ["PrincipalId", "CredentialId", "RequesterDetails"],
    "properties": {"source": SKUPD, "rows": props, "note": note.group(1)},
    "examples": ["topic:ai-model-billing-examples", "topic:ai-model-identity-examples", "topic:ai-prompt-caching-examples"],
    "queries": TOKEN_QUERIES,
    "decided": DECIDED,
    "gaps": GAPS,
    "threads": threads,
}
(SITE / "focus" / "ai-tokens.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"wrote ai-tokens.json: {len(props)} properties, {len(GAPS)} gaps, {len(threads)} threads")
