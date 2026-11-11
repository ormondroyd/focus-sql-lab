"""Build the Data model's history: the pull requests that changed each definition in the FOCUS specification.

Usage: GH_TOKEN=<token> python -I extract_history.py <FOCUS_Spec clone with full history> <commit> <site dir> [cache.json]
Reads  <site dir>/focus/model.json (each dataset, column and relationship records its source file)
Writes <site dir>/focus/history.json

For each source file, git log --follow lists the commits that changed it, following renames. The specification merges
pull requests as single commits whose subject ends "(#N)", which names the pull request. GitHub's API supplies each
pull request's title, author, discussion counts and description, and the same for the issue its title names
(as in "FR #982: ..."). Each summary is an excerpt of the pull request's own description, or of its issue's where the
pull request has none. Nothing is written by the lab: the excerpts are cut at a sentence end, with Markdown link and
emphasis marks removed.
"""

import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.request

REPO, COMMIT, SITE = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
CACHE = pathlib.Path(sys.argv[4]) if len(sys.argv) > 4 else None
OWNER, NAME = "FinOps-Open-Cost-and-Usage-Spec", "FOCUS_Spec"
WIDE = 15  # a pull request that changed more files than this is shown as a spec-wide change


def git(*args):
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, check=True).stdout


model = json.loads((SITE / "focus" / "model.json").read_text())
paths = sorted({d["source"] for d in model["datasets"]}
               | {c["source"] for d in model["datasets"] for c in d["columns"]}
               | {r["source"] for r in model["relationships"]})

# ---- Which pull requests changed each file -------------------------------------------------------------------
files = {}
for path in paths:
    prs, unlinked, sha, subject = {}, 0, None, None
    for line in git("log", "--follow", "--numstat", "--format=@%H\t%s", COMMIT, "--", path).splitlines():
        if line.startswith("@"):
            sha, subject = line[1:].split("\t", 1)
            continue
        if not line.strip() or sha is None:
            continue
        added, deleted = line.split("\t")[:2]
        m = re.search(r"\(#(\d+)\)\s*$", subject)
        if not m:
            unlinked += 1
            continue
        n = int(m.group(1))
        a, d = prs.get(n, (0, 0))
        prs[n] = (a + (int(added) if added.isdigit() else 0), d + (int(deleted) if deleted.isdigit() else 0))
    files[path] = {"prs": [[n, a, d] for n, (a, d) in prs.items()], "unlinked": unlinked}

numbers = sorted({n for f in files.values() for n, _, _ in f["prs"]})
print(f"{len(paths)} files, {len(numbers)} pull requests")

# ---- Pull request and issue details from GitHub ------------------------------------------------------------
cache = json.loads(CACHE.read_text()) if CACHE and CACHE.exists() else {}


def graphql(query):
    req = urllib.request.Request("https://api.github.com/graphql", data=json.dumps({"query": query}).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}"})
    with urllib.request.urlopen(req) as r:
        out = json.load(r)
    if out.get("errors"):
        print("GraphQL errors:", [e.get("message") for e in out["errors"]][:3])
    return out.get("data", {}).get("repository") or {}


ITEM = """... on PullRequest { number title body url createdAt mergedAt changedFiles author { login }
             comments { totalCount } reviews { totalCount } reviewThreads { totalCount }
             closingIssuesReferences(first: 5) { nodes { number } } }
          ... on Issue { number title body url createdAt author { login } comments { totalCount } }"""


def fetch(nums):
    todo = [n for n in nums if str(n) not in cache]
    for i in range(0, len(todo), 40):
        chunk = todo[i:i + 40]
        body = " ".join(f"n{n}: issueOrPullRequest(number: {n}) {{ {ITEM} }}" for n in chunk)
        data = graphql(f'query {{ repository(owner: "{OWNER}", name: "{NAME}") {{ {body} }} }}')
        for n in chunk:
            cache[str(n)] = data.get(f"n{n}")
        print(f"fetched {i + len(chunk)} of {len(todo)}")
    if CACHE:
        CACHE.write_text(json.dumps(cache))


def issue_in_title(title):
    """The issue a pull request's title names, as in "FR #982: ..." or "[AI] #2425: ..."."""
    m = re.match(r"^\s*\[?[A-Za-z]+\]?\s*#(\d+)\b", title or "")
    return int(m.group(1)) if m else None


fetch(numbers)
issues = set()
for n in numbers:
    pr = cache.get(str(n)) or {}
    if issue_in_title(pr.get("title")):
        issues.add(issue_in_title(pr["title"]))
    issues |= {x["number"] for x in (pr.get("closingIssuesReferences") or {}).get("nodes", [])}
fetch(sorted(issues))


def excerpt(body, limit=420):
    """The first paragraph of a description's Summary section, or of the description itself."""
    b = re.sub(r"<!--.*?-->", "", (body or "").replace("\r", ""), flags=re.S)
    m = re.search(r"^#{1,3} *(Summary|Description|Problem|Overview)[^\n]*\n(.*?)(?=^#{1,3} |\Z)", b, re.S | re.M | re.I)
    text = (m.group(2) if m else b).strip()
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    paras = [p for p in paras if not re.match(r"(#|\||- \[|\*\*[^*]+\*\*\s*:?\s*$|>|[*_]*(This PR )?(Closes|Fixes|Resolves))", p, re.I)]
    if not paras:
        return ""
    out = paras[0]
    if out.endswith(":") and len(paras) > 1:  # "the following words:" then a list
        out += " " + "; ".join(l.strip("-* ").strip() for l in paras[1].splitlines()[:4])
    out = re.sub(r"(?m)^\s*[*-]\s+", "• ", out)  # Markdown bullets
    out = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", out)  # Markdown links: keep the text
    out = re.sub(r"(\*\*|__)", "", out)
    out = re.sub(r"\s+", " ", out).strip()
    if len(out) > limit:
        cut = out[:limit]
        out = cut[:cut.rfind(". ") + 1] if ". " in cut[100:] else cut.rstrip() + "…"
    return out


def counts(x):
    return {"comments": (x.get("comments") or {}).get("totalCount", 0),
            "reviews": (x.get("reviews") or {}).get("totalCount", 0),
            "threads": (x.get("reviewThreads") or {}).get("totalCount", 0)}


out_prs, out_issues = {}, {}
for n in numbers:
    pr = cache.get(str(n))
    if not pr:
        continue
    title, body = pr["title"], pr["body"] or ""
    if title.endswith("…") and body.lstrip().startswith("…"):  # GitHub cuts long titles and continues them in the body
        first, _, rest = body.lstrip()[1:].partition("\n")
        title, body = title[:-1].rstrip() + " " + first.strip(), rest
        pr = {**pr, "title": title, "body": body}
    linked = []
    if issue_in_title(pr["title"]):
        linked.append(issue_in_title(pr["title"]))
    linked += [x["number"] for x in pr["closingIssuesReferences"]["nodes"] if x["number"] not in linked]
    summary, source = excerpt(pr["body"]), "pr"
    if not summary:
        for i in linked:
            if cache.get(str(i)) and excerpt(cache[str(i)].get("body")):
                summary, source = excerpt(cache[str(i)]["body"]), f"issue {i}"
                break
    out_prs[n] = {"title": pr["title"], "url": pr["url"], "merged": (pr.get("mergedAt") or "")[:10],
                  "author": (pr.get("author") or {}).get("login"), "files": pr.get("changedFiles"),
                  **counts(pr), "summary": summary, "summary_from": source if summary else None, "issues": linked}
    for i in linked:
        x = cache.get(str(i))
        if x and i not in out_issues:
            out_issues[i] = {"title": x["title"], "url": x["url"], "opened": (x.get("createdAt") or "")[:10],
                             "author": (x.get("author") or {}).get("login"), **counts(x)}

history = {"spec": {"repo": f"https://github.com/{OWNER}/{NAME}", "commit": git("rev-parse", COMMIT).strip()},
           "wide": WIDE, "prs": out_prs, "issues": out_issues, "files": files}
(SITE / "focus" / "history.json").write_text(json.dumps(history, separators=(",", ":")))

focused = [p for p in out_prs.values() if (p["files"] or 0) <= WIDE]
print(f"wrote history.json: {len(out_prs)} pull requests ({len(focused)} focused), {len(out_issues)} issues, "
      f"summaries from the PR: {sum(p['summary_from'] == 'pr' for p in out_prs.values())}, "
      f"from an issue: {sum((p['summary_from'] or '').startswith('issue') for p in out_prs.values())}, "
      f"none: {sum(not p['summary'] for p in out_prs.values())}")
print(f"{(SITE / 'focus' / 'history.json').stat().st_size:,} bytes")
