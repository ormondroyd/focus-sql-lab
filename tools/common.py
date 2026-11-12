"""Shared by summarise.py and recent.py: the models they can use, the checks every AI-written text must pass, and
reading FOCUS_Spec from GitHub's REST API (GH_TOKEN)."""
import json
import os
import re
import sys
import urllib.parse
import urllib.request

REPO = "FinOps-Open-Cost-and-Usage-Spec/FOCUS_Spec"

# Per model: US$ per million input and output tokens (list price), and the request settings. Sonnet 5.5 turns thinking
# off with "between_tools", which no other model accepts. Haiku 5.5 always thinks, so it has room in max_tokens for the
# thinking (billed as output).
MODELS = {
    "claude-sonnet-5-5": {"price": (2.0, 10.0), "thinking": {"type": "between_tools"}, "effort": "medium", "max_tokens": 1024},
    "claude-haiku-5-5": {"price": (0.10, 0.50), "thinking": {"type": "adaptive"}, "effort": "low", "max_tokens": 8000},
}


def model_from(flags, default="claude-sonnet-5-5"):
    """The model and its settings from --model and --effort (low, medium or high)."""
    name = flags[flags.index("--model") + 1] if "--model" in flags else default
    if name not in MODELS:
        sys.exit(f"--model must be one of {', '.join(MODELS)}")
    settings = dict(MODELS[name])
    if "--effort" in flags:  # how hard Haiku thinks; on Sonnet (thinking off) it only shapes the reply
        settings["effort"] = flags[flags.index("--effort") + 1]
        if settings["effort"] not in ("low", "medium", "high"):
            sys.exit("--effort must be low, medium or high")
    return name, settings


# ---- checks -----------------------------------------------------------------------------------------------------
GENDERED = re.compile(r"\b(he|she|him|her|his|hers|himself|herself)\b", re.I)
norm = lambda s: re.sub(r"\s+", " ", s.replace("’", "'").replace("“", '"').replace("”", '"')).strip().lower()
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
# The people in a thread, from the headers the thread text is written with ("Comment by X on ...").
PEOPLE = re.compile(r"^(?:\[\w+\] )?(?:Comment|Review|Inline comment) by ([A-Za-z0-9][A-Za-z0-9-]*)"
                    r"|^(?:\[\w+\] )?(?:Pull request|Issue) opened by ([A-Za-z0-9][A-Za-z0-9-]*)", re.M)


def problems(text, limit, source, thread=False):
    """What's wrong with an AI-written text: an empty list if it passes."""
    found = []
    if thread:
        for user in {a or b for a, b in PEOPLE.findall(source)}:
            for m in re.finditer(rf"(?<![A-Za-z0-9-]){re.escape(user)}(?![A-Za-z0-9-])", text, re.I):
                if m.group(0) != user:
                    found.append(f"it writes the username {user} as {m.group(0)}; write it exactly as shown")
                    break
        if re.search(rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b(?:{MONTHS}) \d{{1,2}}(?:st|nd|rd|th)?\b", text):
            found.append("write dates as 29 October 2026, or as a month and year")
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


# ---- GitHub -----------------------------------------------------------------------------------------------------
def gh(path, **params):
    query = ("&" if "?" in path else "?") + urllib.parse.urlencode(params) if params else ""
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}{query}",
                                 headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def gh_all(path, **params):
    out, page = [], 1
    while True:
        batch = gh(path, per_page=100, page=page, **params)
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def cut(s, n=3000):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + " […cut]"


def is_bot(user):
    return (user or {}).get("type") == "Bot" or (user or {}).get("login", "").endswith("[bot]")
