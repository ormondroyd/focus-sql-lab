"""Recent discussion: the FOCUS_Spec issues and pull requests people discussed in the last two weeks.

    GH_TOKEN=... python -I tools/recent.py <site dir>                         dry run: what's in the window, what's due
    GH_TOKEN=... ANTHROPIC_API_KEY=... python -I tools/recent.py <site dir> --write [--model M] [--effort E]
    GH_TOKEN=... python -I tools/recent.py <site dir> --write --no-ai         write recent.json without calling the API

Reads <site dir>/focus/model.json and focus/history.json; reads and writes <site dir>/recent.json. The daily workflow
(.github/workflows/daily.yml) runs it.

A thread is in the window if someone opened it, commented on it or reviewed it in the last 14 days. Each gets a summary
of that fortnight and a one-line gist of each comment and review, from one call to the model (default Claude Haiku 5.5),
checked like the other summaries (common.problems). A thread is summarised again only when it gains comments or reviews
from people, so earlier summaries are kept from one run to the next. GitHub Actions' "Project Update" comments are kept
as status changes; other bot comments are left out. Comments from before the window aren't fetched: the page links to
the thread on GitHub. A thread is linked to the parts of the data model whose files its pull request changed, and to
those its title, description or recent comments name (a column's ID, a dataset's name).
"""
import datetime
import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).parent))  # python -I leaves the script's folder off the path
from common import cut, gh_all, is_bot, model_from, norm, problems  # noqa: E402

SITE, FLAGS = pathlib.Path(sys.argv[1]), sys.argv[2:]
DAYS = 14
NOW = datetime.datetime.now(datetime.timezone.utc)
SINCE = (NOW - datetime.timedelta(days=DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
OUT = SITE / "recent.json"
MODEL, SETTINGS = model_from(FLAGS, default="claude-haiku-5-5")
SUMMARY_WORDS, GIST_WORDS = 90, 30

model = json.loads((SITE / "focus" / "model.json").read_text())
history = json.loads((SITE / "focus" / "history.json").read_text())
before = json.loads(OUT.read_text()) if OUT.exists() else {"threads": []}
kept = {t["number"]: t for t in before["threads"]}

# ---- the parts of the data model, by file and by the words that name them -----------------------------------------
by_file, by_word = defaultdict(list), {}
CAMEL = re.compile(r"[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]*)+")  # BilledCost, SkuPriceDetails: not plain English words
for d in model["datasets"]:
    by_file[d["source"]].append(f"dataset:{d['id']}")
    by_word.setdefault(d["id"], f"dataset:{d['id']}")
    by_word.setdefault(d["name"], f"dataset:{d['id']}")  # "Cost and Usage", "SKU Price"
    for c in d["columns"]:
        by_file[c["source"]].append(f"column:{d['id']}.{c['id']}")
        if CAMEL.fullmatch(c["id"]):
            by_word.setdefault(c["id"], f"column:{d['id']}.{c['id']}")  # the first dataset that has it (Cost and Usage first)
for kind in ("attributes", "conditions"):
    for a in model.get(kind, []):
        if not a.get("id"):  # the conditions overview page has no ID of its own
            continue
        key = f"{kind[:-1]}:{a['id']}"
        by_file[a["source"]].append(key)
        by_word.setdefault(a["id"], key)
for t in model.get("topics", []):
    for f in t["files"] or [t["source"]]:
        by_file[f].append(f"topic:{t['id']}")
by_word = {w: k for w, k in by_word.items() if len(w) >= 4}
WORDS = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(sorted(map(re.escape, by_word), key=len, reverse=True)) + r")(?![A-Za-z0-9_])")
REF = re.compile(r"(?<![\w&/#])#(\d{2,5})\b|FOCUS_Spec/(?:issues|pull)/(\d+)")


def plain(text, n=220):
    """A short plain-text excerpt: no quoted replies, code, links or Markdown marks."""
    text = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(">"))
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[*_`#|]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[:n].rsplit(" ", 1)[0] + "…"


def status_lines(body):
    """GitHub Actions' "Project Update" comment, as plain lines ("Review Bot updated PR Approvals: 2 → 3")."""
    if "Project Update" not in (body or ""):
        return None
    lines = [re.sub(r"\*\*", "", line.strip().lstrip("*").strip()) for line in body.splitlines()]
    return [line for line in lines if line and "Project Update" not in line]


# ---- what happened in the window -----------------------------------------------------------------------------------
threads = {i["number"]: i for i in gh_all("issues", state="all", since=SINCE)}  # issues and pull requests
events = defaultdict(list)
window_comments = Counter()
for c in gh_all("issues/comments", since=SINCE):
    if c["created_at"] < SINCE:
        continue  # an older comment edited in the window
    n = int(c["issue_url"].rsplit("/", 1)[1])
    window_comments[n] += 1
    if is_bot(c["user"]):
        lines = status_lines(c["body"])
        if lines:
            events[n].append({"id": f"s{c['id']}", "kind": "status", "at": c["created_at"], "url": c["html_url"], "lines": lines})
        continue
    events[n].append({"id": f"c{c['id']}", "kind": "comment", "author": c["user"]["login"], "at": c["created_at"],
                      "url": c["html_url"], "body": c["body"] or ""})
for c in gh_all("pulls/comments", since=SINCE):
    if c["created_at"] < SINCE or is_bot(c["user"]):
        continue
    n = int(c["pull_request_url"].rsplit("/", 1)[1])
    parent = f"i{c['in_reply_to_id']}" if c.get("in_reply_to_id") else f"r{c['pull_request_review_id']}" if c.get("pull_request_review_id") else None
    events[n].append({"id": f"i{c['id']}", "kind": "inline", "author": c["user"]["login"], "at": c["created_at"],
                      "url": c["html_url"], "path": c["path"], "body": c["body"] or "", "parent": parent})
for n, i in threads.items():
    if i["created_at"] >= SINCE and not is_bot(i["user"]):
        events[n].append({"id": f"o{n}", "kind": "opened", "author": i["user"]["login"], "at": i["created_at"],
                          "url": i["html_url"], "body": i.get("body") or ""})
    if "pull_request" in i:
        for r in gh_all(f"pulls/{n}/reviews"):
            if (r.get("submitted_at") or "") >= SINCE and not is_bot(r["user"]) and (r.get("body") or r["state"] != "COMMENTED"):
                events[n].append({"id": f"r{r['id']}", "kind": "review", "state": r["state"].lower().replace("_", " "),
                                  "author": r["user"]["login"], "at": r["submitted_at"], "url": r["html_url"], "body": r.get("body") or ""})

feed = []
known = {**history["prs"], **history["issues"]}  # titles for threads outside the window
for n, evs in events.items():
    evs.sort(key=lambda e: e["at"])
    people = [e for e in evs if e["kind"] != "status"]
    if not people or n not in threads:
        continue
    i = threads[n]
    ids = {e["id"] for e in evs}
    # Replies: an inline comment answers the one it replies to, or sits under its review; a comment that opens by
    # quoting an earlier one, or by @-mentioning its author, answers that comment.
    for k, e in enumerate(evs):
        if e["kind"] == "inline":
            e["parent"] = e["parent"] if e["parent"] in ids else None
        elif e["kind"] == "comment":
            first = next((line.lstrip("> ").strip() for line in e["body"].splitlines() if line.strip()), "")
            earlier = [x for x in evs[:k] if x["kind"] in ("comment", "opened", "review")]
            if e["body"].lstrip().startswith(">") and len(first) >= 15:
                e["parent"] = next((x["id"] for x in reversed(earlier) if norm(first) in norm(x["body"])), None)
            elif m := re.match(r"\s*@([A-Za-z0-9-]+)", e["body"]):
                e["parent"] = next((x["id"] for x in reversed(earlier) if x.get("author", "").lower() == m.group(1).lower()), None)
    pr = i.get("pull_request")
    state = ("merged" if pr.get("merged_at") else "closed") if pr and i["state"] == "closed" else \
        ("draft" if i.get("draft") else "open") if i["state"] == "open" else (i.get("state_reason") or "closed").replace("_", " ")
    text = "\n".join([i["title"], i.get("body") or ""] + [e.get("body", "") for e in people])
    words = Counter(by_word[w] for w in WORDS.findall(text))
    files = [f["filename"] for f in gh_all(f"pulls/{n}/files")] if pr else []
    from_files = [k for f in files for k in by_file.get(f, [])]
    objects = list(dict.fromkeys(from_files + [k for k, _ in words.most_common()]))[:10]
    refs = list(dict.fromkeys(int(a or b) for a, b in REF.findall(text) if int(a or b) != n))[:12]
    feed.append({
        "number": n, "kind": "pr" if pr else "issue", "title": i["title"], "url": i["html_url"], "state": state,
        "labels": [label["name"] for label in i.get("labels", [])], "author": i["user"]["login"], "opened": i["created_at"][:10],
        "last": people[-1]["at"], "earlier": max(0, i.get("comments", 0) - window_comments[n]),
        "objects": objects, "files_matched": bool(from_files),
        "refs": [{"n": r, "title": (threads.get(r) or known.get(str(r)) or {}).get("title")} for r in refs],
        "basis": sorted(e["id"] for e in people),
        "events": evs,
    })
feed.sort(key=lambda t: t["last"], reverse=True)

# ---- summaries ----------------------------------------------------------------------------------------------------
for t in feed:
    old = kept.get(t["number"])
    if old and old.get("basis") == t["basis"] and old.get("summary"):
        t["summary"], t["gists"] = old["summary"], old.get("gists", {})
due = [t for t in feed if "summary" not in t]


def source_text(t):
    i = threads[t["number"]]
    head = [f"Title: #{t['number']} {t['title']}",
            f"{'Pull request' if t['kind'] == 'pr' else 'Issue'} opened by {t['author']} on {t['opened']}. State: {t['state']}.",
            "Description:\n" + cut(i.get("body"), 4000),
            f"\nActivity in the last {DAYS} days, oldest first. Each item starts with its ID in brackets."]
    lines = []
    for e in t["events"]:
        reply = f" (reply to {e['parent']})" if e.get("parent") else ""
        if e["kind"] == "status":
            lines.append(f"[{e['id']}] Status change on {e['at'][:10]}: " + "; ".join(e["lines"]))
        elif e["kind"] == "opened":
            lines.append(f"[{e['id']}] {'Pull request' if t['kind'] == 'pr' else 'Issue'} opened by {e['author']} on {e['at'][:10]} (the description above).")
        elif e["kind"] == "review":
            lines.append(f"[{e['id']}] Review by {e['author']} ({e['state']}) on {e['at'][:10]}{reply}:\n{cut(e['body'])}")
        elif e["kind"] == "inline":
            lines.append(f"[{e['id']}] Inline comment by {e['author']} on {e['path']}, {e['at'][:10]}{reply}:\n{cut(e['body'], 1500)}")
        else:
            lines.append(f"[{e['id']}] Comment by {e['author']} on {e['at'][:10]}{reply}:\n{cut(e['body'])}")
    return "\n".join(head) + "\n\n" + "\n\n".join(lines)


chars = sum(len(source_text(t)) for t in due)
p_in, p_out = SETTINGS["price"]
print(f"{len(threads)} issues and pull requests changed since {SINCE[:10]}; {len(feed)} had people opening, commenting or "
      f"reviewing; {len(due)} need a summary (about {chars // 4 + 1200 * len(due):,} input tokens, "
      f"US${(chars // 4 + 1200 * len(due)) * p_in / 1e6 + 600 * len(due) * p_out / 1e6:.2f} at list price with {MODEL}, before thinking).")
for t in due[:20]:
    print(f"  #{t['number']} {t['title'][:70]} ({len(t['basis'])} items)")

if "--write" not in FLAGS:
    sys.exit()

RULES = """You summarise recent activity in GitHub threads from the FOCUS specification repository (FinOps Open Cost and Usage Specification) for a daily digest. The reader follows the working group and wants to know what happened in the last two weeks without opening the thread.

Return:
- summary: what this thread's activity in the last two weeks was about, in plain English and the past tense: what was proposed, asked or changed, who held which position (by GitHub username), anything agreed or decided, and what the thread says happens next. Use the description only as background for what is new.
- gists: one entry for each item in the activity list except status changes, with its ID, saying in one sentence what that item said, asked or decided. A review that only approves can say so briefly.

Rules:
- State only what the thread says. Don't speculate, evaluate or add background knowledge.
- Name people only by their GitHub username exactly as shown, with the same capital and small letters even at the start of a sentence. Never guess real names. Refer to people by username or with they/them, never he or she.
- Refer to other issues and pull requests as #123. No URLs, no Markdown, no emoji.
- Write dates as 29 October 2026, or as a month and year (October 2026).
- Paraphrase. Quote at most 10 words, and only when the exact wording matters.
- The summary is at most 90 words. Each gist is at most 30 words."""

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["summary", "gists"], "properties": {
    "summary": {"type": "string"},
    "gists": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["id", "gist"],
                                         "properties": {"id": {"type": "string"}, "gist": {"type": "string"}}}}}}

spent_in = spent_out = 0
written = partly = failed = 0
if "--no-ai" not in FLAGS and due:
    import anthropic

    client = anthropic.Anthropic()

    def review(data, src, ids):
        """The checks' findings, and the parts that pass."""
        found, ok = [], {}
        summary_problems = problems(data.get("summary", ""), SUMMARY_WORDS, src, thread=True)
        found += [f"summary: {p}" for p in summary_problems]
        got = {g["id"]: g["gist"].strip() for g in data.get("gists", [])}
        for i in ids:
            if i not in got:
                found.append(f"there is no gist for {i}")
                continue
            gist_problems = problems(got[i], GIST_WORDS, src, thread=True)
            found += [f"gist {i}: {p}" for p in gist_problems]
            if not gist_problems:
                ok[i] = got[i]
        return found, (data.get("summary", "").strip() if not summary_problems else None), ok

    for t in due:
        src = source_text(t)
        ids = [e["id"] for e in t["events"] if e["kind"] != "status"]
        messages = [{"role": "user", "content": src}]
        try:
            for attempt in (1, 2):
                r = client.messages.create(model=MODEL, max_tokens=16000, system=RULES, messages=messages,
                                           thinking=SETTINGS["thinking"],
                                           output_config={"effort": SETTINGS["effort"], "format": {"type": "json_schema", "schema": SCHEMA}})
                spent_in += r.usage.input_tokens
                spent_out += r.usage.output_tokens
                reply = next((b.text for b in r.content if b.type == "text"), "")
                if r.stop_reason != "end_turn":
                    found, summary, gists = [f"the reply stopped early ({r.stop_reason})"], None, {}
                else:
                    found, summary, gists = review(json.loads(reply), src, ids)
                if not found:
                    break
                messages += [{"role": "assistant", "content": reply},
                             {"role": "user", "content": "That reply fails these checks: " + "; ".join(found)
                              + ". Rewrite it so every part passes, following the same rules."}]
        except anthropic.AuthenticationError:
            raise
        except Exception as e:  # one thread's error (the API, or GitHub's rate limit) doesn't lose the run
            found, summary, gists = [f"error: {type(e).__name__}: {str(e)[:200]}"], None, {}
        if summary:
            t["summary"], t["gists"] = summary, gists
            written += not found
            partly += bool(found)
        else:
            failed += 1
            if t["number"] in kept and kept[t["number"]].get("summary"):  # keep yesterday's rather than nothing
                t["summary"], t["gists"] = kept[t["number"]]["summary"], kept[t["number"]].get("gists", {})
                t["stale"] = True
        print(f"#{t['number']}: " + ("written" if summary and not found else "written, some gists failed" if summary else "not written")
              + (": " + "; ".join(found)[:300] if found else ""))

# ---- write -------------------------------------------------------------------------------------------------------
for t in feed:
    for e in t["events"]:
        if e["kind"] != "status":
            e["excerpt"] = plain(e.pop("body", ""))  # shown when an item has no gist
OUT.write_text(json.dumps({
    "generated_at": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"), "since": SINCE, "days": DAYS,
    "model": MODEL if written or partly else before.get("model"),
    "about": ("FOCUS_Spec issues and pull requests that people opened, commented on or reviewed in the last "
              f"{DAYS} days. Each summary and one-line gist is written by an AI model from the thread, and rewritten when "
              "the thread gains comments or reviews: check the thread before relying on one. Status changes are posted by "
              "the repository's own automation."),
    "threads": feed,
}, indent=1, ensure_ascii=False))
cost = spent_in * p_in / 1e6 + spent_out * p_out / 1e6
print(f"Wrote {OUT}: {len(feed)} threads. Summaries: {written} written, {partly} with some gists missing, {failed} failed, "
      f"{len(feed) - len(due)} kept. Used {spent_in:,} input and {spent_out:,} output tokens with {MODEL}: "
      f"US${cost:.4f} at list price.")
