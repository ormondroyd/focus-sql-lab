"""Keep the AI-written summaries up to date: write them only for spec pages and GitHub threads that are new or changed.

    python tools/summarise.py <FOCUS_Spec checkout> <site dir>                 dry run: list what's due, with an estimated cost
    python tools/summarise.py <FOCUS_Spec checkout> <site dir> --write [--limit N]   write up to N summaries (default 50)
        [--model M]       claude-sonnet-5-5 (default) or claude-haiku-5-5
        [--effort E]      low, medium or high (default: medium for Sonnet, low for Haiku)
        [--only K1,K2]    write exactly these page keys or thread numbers, due or not (to compare models, say)
    python tools/summarise.py <FOCUS_Spec checkout> <site dir> --stamp         only write site/focus/refresh.json
    python tools/summarise.py <FOCUS_Spec checkout> <site dir> --init          record the current pages and threads as summarised

Summaries live in site/object-summaries.json (one per dataset, column, attribute, condition and supporting topic page)
and site/thread-summaries.json (one per FOCUS_Spec issue and pull request in history.json with three or more comments or
reviews). tools/summary-basis.json records what each was written from: a hash of the page, or the thread's comment and
review counts. A page whose hash changes, or a thread that gains comments or reviews, is due again.

--write calls the Claude API (ANTHROPIC_API_KEY) and costs money; nothing else here does. It also needs GH_TOKEN to read
threads. Every summary must pass the checks in problems() (word limit, they/them, no URLs or Markdown, quotes verbatim);
one that fails twice is skipped and reported.
"""
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.request

SPEC, SITE = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
FLAGS = sys.argv[3:]
LIMIT = int(FLAGS[FLAGS.index("--limit") + 1]) if "--limit" in FLAGS else 50
BASIS = pathlib.Path(__file__).parent / "summary-basis.json"
OBJ, THR = SITE / "object-summaries.json", SITE / "thread-summaries.json"
REPO = "FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec"
# Per model: US$ per million input and output tokens (list price), and the request settings. Sonnet 5.5 turns thinking
# off with "between_tools", which no other model accepts. Haiku 5.5 always thinks, so it runs at low effort with room in
# max_tokens for the thinking (billed as output).
MODELS = {
    "claude-sonnet-5-5": {"price": (2.0, 10.0), "thinking": {"type": "between_tools"}, "effort": "medium", "max_tokens": 1024},
    "claude-haiku-5-5": {"price": (0.10, 0.50), "thinking": {"type": "adaptive"}, "effort": "low", "max_tokens": 8000},
}
MODEL = FLAGS[FLAGS.index("--model") + 1] if "--model" in FLAGS else "claude-sonnet-5-5"
if MODEL not in MODELS:
    sys.exit(f"--model must be one of {', '.join(MODELS)}")
PRICE_IN, PRICE_OUT = MODELS[MODEL]["price"]
if "--effort" in FLAGS:  # how hard Haiku thinks; on Sonnet (thinking off) it only shapes the reply
    MODELS[MODEL]["effort"] = FLAGS[FLAGS.index("--effort") + 1]
    if MODELS[MODEL]["effort"] not in ("low", "medium", "high"):
        sys.exit("--effort must be low, medium or high")
ONLY = [k.strip() for k in (FLAGS[FLAGS.index("--only") + 1] if "--only" in FLAGS else "").split(",") if k.strip()]
TODAY = datetime.date.today().isoformat()

model = json.loads((SITE / "focus" / "model.json").read_text())
history = json.loads((SITE / "focus" / "history.json").read_text())
objs, threads = json.loads(OBJ.read_text()), json.loads(THR.read_text())
basis = json.loads(BASIS.read_text()) if BASIS.exists() else {"pages": {}, "threads": {}}

# ---- what should have a summary -------------------------------------------------------------------------------
LIMITS = {"dataset": 200, "column": 100, "attribute": 200, "condition": 100, "appendix": 160, "metadata": 160, "schema": 160}
pages = {}  # key -> (kind, [files], what it defines)
for d in model["datasets"]:
    pages[d["source"]] = ("dataset", [d["source"]], f"dataset {d['id']} ({d['name']})")
    for c in d["columns"]:
        pages[c["source"]] = ("column", [c["source"]], f"column {d['id']}.{c['id']} ({c['name']})")
for a in model["attributes"]:
    pages[a["source"]] = ("attribute", [a["source"]], f"attribute {a['id']}")
for c in model["conditions"]:
    pages[c["source"]] = ("condition", [c["source"]], f"operating model condition {c['id']}")
for t in model["topics"]:
    pages["topic:" + t["id"]] = (t["kind"], t["files"] or [t["source"]], f"{t['kind']} topic {t['name']}")


def page_hash(files):
    h = hashlib.sha256()
    for f in files:
        h.update(f.encode() + b"\0" + (SPEC / f).read_bytes())
    return h.hexdigest()[:16]


everything = {**history["prs"], **history["issues"]}
weight = {n: v.get("comments", 0) + v.get("reviews", 0) for n, v in everything.items()}
due_threads_all = {n for n, w in weight.items() if w >= 3}
counts = lambda n: f"{everything[n].get('comments', 0)}/{everything[n].get('reviews', 0)}"

if "--init" in FLAGS:
    basis = {"pages": {k: page_hash(f) for k, (_, f, _) in pages.items() if k in objs["summaries"]},
             "threads": {n: counts(n) for n in due_threads_all if n in threads["summaries"]}}
    BASIS.write_text(json.dumps(basis, indent=0, sort_keys=True))
    print(f"recorded {len(basis['pages'])} pages and {len(basis['threads'])} threads as summarised")
    sys.exit()


def stamp():
    """site/focus/refresh.json: which spec commit the site was built from, and when things were last refreshed."""
    out = SITE / "focus" / "refresh.json"
    old = json.loads(out.read_text()) if out.exists() else {}
    # The time of the rebuild, in UTC; the page shows it in the reader's own time zone.
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    refreshed = now if "--data" in FLAGS else old.get("refreshed_at", now)
    out.write_text(json.dumps({"spec": model["spec"], "refreshed_at": refreshed,
                               "summaries_written": {"pages": objs.get("written"), "threads": threads.get("written")}}, indent=1))


if "--stamp" in FLAGS:
    stamp()
    sys.exit()

new_pages = [k for k in pages if k not in objs["summaries"]]
changed_pages = [k for k in pages if k in objs["summaries"] and basis["pages"].get(k) != page_hash(pages[k][1])]
new_threads = sorted((n for n in due_threads_all if n not in threads["summaries"]), key=int)
changed_threads = sorted((n for n in due_threads_all if n in threads["summaries"] and basis["threads"].get(n) != counts(n)), key=int)
due = [("page", k) for k in new_pages + changed_pages] + [("thread", n) for n in new_threads + changed_threads]
if ONLY:
    unknown = [k for k in ONLY if k not in pages and k not in due_threads_all]
    if unknown:
        sys.exit(f"--only: not a page key or a thread with three or more comments or reviews: {', '.join(unknown)}")
    due = [("page" if k in pages else "thread", k) for k in ONLY]


def estimate(kind, key):
    """Rough tokens in and out: about four characters a token, plus the instructions."""
    if kind == "page":
        chars = sum(len((SPEC / f).read_text()) for f in pages[key][1])
        return 900 + chars // 4, 300
    return 900 + min(400 + 250 * weight[key], 30_000), 200  # thread_text() keeps at most 120,000 characters


tin, tout = map(sum, zip(*(estimate(*d) for d in due))) if due else (0, 0)
print(f"Due: {len(new_pages)} new and {len(changed_pages)} changed pages, {len(new_threads)} new and "
      f"{len(changed_threads)} changed threads ({len(new_pages + changed_pages + new_threads + changed_threads)} summaries).")
if ONLY:
    print(f"--only: writing just these {len(due)}.")
print(f"Estimated cost of writing all of them with {MODEL}: about {tin:,} input and {tout:,} output tokens, "
      f"US${tin * PRICE_IN / 1e6 + tout * PRICE_OUT / 1e6:.2f} at list price.")
for kind, key in due[:30]:
    print(f"  {kind}: {key}")
if len(due) > 30:
    print(f"  … and {len(due) - 30} more")
if "--write" not in FLAGS or not due:
    sys.exit()

# ---- writing ---------------------------------------------------------------------------------------------------
import anthropic  # only needed to write

THREAD_RULES = """You write summaries of GitHub discussion threads from the FOCUS specification repository (FinOps Open Cost and Usage Specification) for a learning website. The reader wants to know what each conversation was about and how it ended.

Cover, in plain English and the past tense:
1. What was proposed or asked, and why.
2. The main points raised or disputed: who held which position (by GitHub username), alternatives considered, concerns, compromises.
3. How it ended: merged, approved by members, closed as complete, deferred, cut from a release, superseded by another issue or pull request, or still open. Give the month and year when the thread states it.

Rules:
- State only what the thread says. Don't speculate, evaluate or add background knowledge. If the thread doesn't record the outcome, say "The thread doesn't record the outcome."
- Name people only by their GitHub username exactly as shown. Never guess real names. Refer to people by username or with they/them, never he or she.
- Refer to other issues and pull requests as #123. No URLs, no Markdown, no emoji, no bullet lists.
- Paraphrase. Quote at most 10 words, and only when the exact wording matters.
- Skip bot comments, CLA notices and routine housekeeping (scheduling, moving to member review, reassigning) unless they record a decision or the outcome.
- If a thread is mostly editorial or mechanical, say so briefly.

Reply with the summary text only."""

PAGE_RULES = """You write plain-language summaries of pages from the FOCUS specification (FinOps Open Cost and Usage Specification) for a learning website's data model view. The reader is a technical product manager who wants to understand each part of the model without reading the page itself. Accuracy matters more than style: every statement must come from the page.

What to cover:
- A dataset page: what the dataset records and what it's for; what one row represents and what makes a row unique, if the page says; when a data generator must or may provide it; how it connects to other datasets; anything notable, such as preview status or a key rule.
- A column page: what the value means in practice; its data type and format, and its allowed values (summarise a long list and name a few); its feature level as the page gives it and when it is required, may be null, or must be null; how it relates to other columns; any rule a user could easily get wrong.
- An attribute, operating model condition, appendix, metadata or schema page: what it is, what it governs or shows, and the rules or examples a reader most needs.

Rules:
- Use only what the page says. Don't add background knowledge, examples or rules the page doesn't contain.
- Translate the normative language faithfully: MUST and MUST NOT become "must" and "must not", SHOULD becomes "should", MAY becomes "may". Don't strengthen or weaken them.
- Plain, precise English in the present tense, as continuous prose: no Markdown, no bullet lists, no URLs, no links. Write column and dataset IDs exactly as the spec does, and spell out other abbreviations.
- Start with what the thing is.

Reply with the summary text only."""

GENDERED = re.compile(r"\b(he|she|him|her|his|hers|himself|herself)\b", re.I)
norm = lambda s: re.sub(r"\s+", " ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()


def problems(text, limit, source):
    found = []
    if not text:
        found.append("the reply was empty")
    if len(text.split()) > limit:
        found.append(f"it has {len(text.split())} words; the limit is {limit}")
    if GENDERED.search(text):
        found.append("it uses he or she; use the username or they/them")
    if re.search(r"https?://|www\.", text):
        found.append("it contains a URL")
    if re.search(r"\*\*|`|^\s*[-*•] |\[[^\]]+\]\(|^#+ ", text, re.M):
        found.append("it contains Markdown or a list")
    for q in re.findall(r"[\"“]([^\"”]{12,})[\"”]", text):
        if norm(q) not in norm(source):
            found.append(f"the quote \"{q[:60]}\" isn't in the source word for word")
    return found


def gh(path):
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}",
                                 headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def gh_all(path):
    out, page = [], 1
    while True:
        batch = gh(f"{path}?per_page=100&page={page}")
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def cut(s, n=3000):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + " […cut]"


def thread_text(n):
    i = gh(f"issues/{n}")
    is_pr = "pull_request" in i
    head = [f"Title: #{n} {i['title']}", f"{'Pull request' if is_pr else 'Issue'} opened by {i['user']['login']} on {i['created_at'][:10]}."]
    if is_pr:
        p = gh(f"pulls/{n}")
        head.append(f"Merged on {p['merged_at'][:10]}." if p.get("merged_at") else f"State: {p['state']}.")
    else:
        head.append(f"State: {i['state']}{' (' + i['state_reason'] + ')' if i.get('state_reason') else ''}.")
    head.append("Description:\n" + cut(i.get("body"), 6000))
    events = []
    bot = lambda u: u.get("type") == "Bot" or u["login"].endswith("[bot]")
    for c in gh_all(f"issues/{n}/comments"):
        if not bot(c["user"]):
            events.append((c["created_at"], f"Comment by {c['user']['login']} on {c['created_at'][:10]}:\n{cut(c['body'])}"))
    if is_pr:
        for r in gh_all(f"pulls/{n}/reviews"):
            if r.get("submitted_at") and not bot(r["user"]) and (r.get("body") or r["state"] != "COMMENTED"):
                events.append((r["submitted_at"], f"Review by {r['user']['login']} ({r['state'].lower()}) on {r['submitted_at'][:10]}:\n{cut(r.get('body'))}"))
        for c in gh_all(f"pulls/{n}/comments"):
            if not bot(c["user"]):
                events.append((c["created_at"], f"Inline comment by {c['user']['login']} on {c['path']}, {c['created_at'][:10]}:\n{cut(c['body'], 1500)}"))
    text = "\n\n".join(head + [e for _, e in sorted(events)])
    return text[:120_000]


def page_text(key):
    kind, files, what = pages[key]
    body = "\n\n".join(f"--- {f} ---\n{(SPEC / f).read_text()}" for f in files)
    return f"This page defines: {what}.\n\n{body[:120_000]}"


client = anthropic.Anthropic()
spent_in = spent_out = 0


def write_one(system, content, limit):
    """One summary, checked; one retry with the problems named. Returns (text, problems)."""
    global spent_in, spent_out
    messages = [{"role": "user", "content": f"{content}\n\nLength: at most {limit} words."}]
    m = MODELS[MODEL]
    for attempt in (1, 2):
        # The retry sends back only the text of the first reply, not its thinking, which the API allows.
        r = client.messages.create(model=MODEL, max_tokens=m["max_tokens"], system=system, messages=messages,
                                   thinking=m["thinking"], output_config={"effort": m["effort"]})
        spent_in += r.usage.input_tokens
        spent_out += r.usage.output_tokens
        text = "".join(b.text for b in r.content if b.type == "text").strip()
        found = problems(text, limit, content) if r.stop_reason == "end_turn" else [f"the reply stopped early ({r.stop_reason})"]
        if not found or attempt == 2:
            return text, found
        messages += [{"role": "assistant", "content": text},
                     {"role": "user", "content": "That summary fails these checks: " + "; ".join(found) + ". Rewrite it so it passes, following the same rules. Reply with the summary text only."}]


skipped = []
for kind, key in due[:LIMIT]:
    if kind == "page":
        text, found = write_one(PAGE_RULES, page_text(key), LIMITS.get(pages[key][0], 160))
        if not found:
            objs["summaries"][key] = text
            basis["pages"][key] = page_hash(pages[key][1])
    else:
        text, found = write_one(THREAD_RULES, thread_text(key), 70 if weight[key] < 20 else 130)
        if not found:
            threads["summaries"][key] = text
            basis["threads"][key] = counts(key)
    print(("skipped " if found else "wrote ") + f"{kind} {key}" + (": " + "; ".join(found) if found else ""))
    if found:
        skipped.append(key)

objs["written"] = threads["written"] = TODAY
objs["about"] = ("Plain-language summaries of the FOCUS specification's dataset, column, attribute, condition, appendix, metadata "
                 "and schema pages, written by Claude (an AI model) from each page, and rewritten when the page changes.")
threads["about"] = ("Summaries of the conversation in each FOCUS_Spec issue and pull request in the Data model's history that has "
                    "three or more comments or reviews, written by Claude (an AI model) from each thread, and rewritten when it "
                    "gains comments or reviews. They paraphrase the discussion and name participants by GitHub username.")
OBJ.write_text(json.dumps(objs, indent=1, ensure_ascii=False))
THR.write_text(json.dumps(threads, indent=1, ensure_ascii=False))
BASIS.write_text(json.dumps(basis, indent=0, sort_keys=True))
stamp()
cost = spent_in * PRICE_IN / 1e6 + spent_out * PRICE_OUT / 1e6
print(f"Wrote {min(len(due), LIMIT) - len(skipped)}, skipped {len(skipped)}, {max(0, len(due) - LIMIT)} left for the next run. "
      f"Used {spent_in:,} input and {spent_out:,} output tokens with {MODEL}: US${cost:.4f} at list price.")
