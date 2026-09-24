#!/usr/bin/env python3
"""
Sort a large email export into categories.

Usage:
    python3 sort_emails.py "All mail Including Spam and Trash.mbox"
    python3 sort_emails.py path/to/folder_of_eml_files --out results
    python3 sort_emails.py inbox.mbox --contacts contacts.txt --no-split

Reads a Gmail Google Takeout .mbox file (or a folder of .eml files), sorts
every message with the rules in categories.py, and writes to the output folder:

    all_emails.csv       one row per email: date, sender, subject, category, why
    priority.csv         just the money/press/licensing emails, newest first
    summary.txt          counts per category
    by_category/*.mbox   one mailbox file per category (open in Thunderbird,
                         or re-import into Gmail with a tool of your choice)

Only uses the Python standard library -- no installs needed for this step.
"""

import argparse
import csv
import email
import email.policy
import os
import re
import sys
import time
import zipfile
from collections import Counter
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape

import categories as C
import replies

BODY_CHARS = 3000  # how much of each body the keyword rules look at


# --------------------------------------------------------------------------
# Reading messages
# --------------------------------------------------------------------------

def _split_mbox(f):
    """Yield raw messages from a binary mbox stream, one at a time."""
    buf = []
    prev_blank = True
    for line in f:
        if line.startswith(b"From ") and prev_blank and buf:
            yield b"".join(buf)
            buf = []
        buf.append(line)
        prev_blank = line in (b"\n", b"\r\n")
    if buf:
        yield b"".join(buf)


def iter_mbox(path):
    """Stream raw messages out of an mbox file without loading it into memory.

    Yields (message_number, raw_bytes). Works on multi-gigabyte Takeout files.
    """
    with open(path, "rb") as f:
        yield from enumerate(_split_mbox(f), start=1)


def iter_zip(path):
    """Read every .mbox inside a Google Takeout .zip without unzipping it."""
    with zipfile.ZipFile(path) as zf:
        members = sorted(n for n in zf.namelist() if n.lower().endswith(".mbox"))
        if not members:
            raise ValueError("This zip file has no .mbox email file inside. "
                             "Make sure the Takeout export included Mail.")
        n = 0
        for member in members:
            with zf.open(member) as f:
                for raw in _split_mbox(f):
                    n += 1
                    yield n, raw


def iter_eml_dir(path):
    n = 0
    for root, _dirs, files in os.walk(path):
        for name in sorted(files):
            if name.lower().endswith(".eml"):
                n += 1
                with open(os.path.join(root, name), "rb") as f:
                    yield n, f.read()


def iter_messages(path):
    if os.path.isdir(path):
        return iter_eml_dir(path)
    if zipfile.is_zipfile(path):
        return iter_zip(path)
    return iter_mbox(path)


def _strip_mbox_from_line(raw):
    if raw.startswith(b"From "):
        nl = raw.find(b"\n")
        return raw[nl + 1:] if nl != -1 else b""
    return raw


def _html_to_text(html):
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    return unescape(re.sub(r"(?s)<[^>]+>", " ", html))


def body_text(msg, limit=BODY_CHARS):
    """Best-effort plain-text body, preferring text/plain over text/html."""
    plain, html = None, None
    for part in msg.walk():
        if part.is_multipart() or part.get_content_disposition() == "attachment":
            continue
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            text = part.get_content()
        except Exception:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode("utf-8", errors="replace")
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and html is None:
            html = text
        if plain is not None:
            break
    text = plain if plain is not None else _html_to_text(html or "")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _header(msg, name):
    try:
        return str(msg.get(name, "") or "")
    except Exception:
        # Malformed encoded headers are common in spam; fall back to raw.
        raw = msg.get_all(name) or [""]
        return str(raw[0])


def parse(raw):
    """Turn raw bytes into a small dict with the fields the rules need."""
    msg = email.message_from_bytes(_strip_mbox_from_line(raw), policy=email.policy.default)
    from_header = _header(msg, "From")
    name, addr = parseaddr(from_header)
    addr = addr.lower()
    date_header = _header(msg, "Date")
    try:
        date = parsedate_to_datetime(date_header).strftime("%Y-%m-%d %H:%M")
    except Exception:
        date = ""
    try:
        body = body_text(msg)
    except Exception:
        body = ""
    return {
        "date": date,
        "from_name": name,
        "from_addr": addr,
        "reply_to": parseaddr(_header(msg, "Reply-To"))[1].lower(),
        "domain": addr.rsplit("@", 1)[-1] if "@" in addr else "",
        "subject": re.sub(r"\s+", " ", _header(msg, "Subject")).strip(),
        "labels": _header(msg, "X-Gmail-Labels"),
        "bulk": bool(_header(msg, "List-Unsubscribe")) or _header(msg, "Precedence").lower() in ("bulk", "list", "junk"),
        "body": body,
    }


# --------------------------------------------------------------------------
# Classifying
# --------------------------------------------------------------------------

def _compile(keyword):
    # Whole words only; a trailing "*" allows any ending ("licens*" -> "licensing").
    wildcard = keyword.endswith("*")
    keyword = keyword.rstrip("*")
    prefix = r"\b" if keyword[:1].isalnum() else ""
    suffix = r"\b" if keyword[-1:].isalnum() and not wildcard else ""
    return re.compile(prefix + re.escape(keyword) + suffix, re.IGNORECASE)


_RULES = {
    cat: [(weight, _compile(kw)) for weight, kws in levels.items() for kw in kws]
    for cat, levels in C.KEYWORDS.items()
}


def _domain_in(domain, domains):
    return any(domain == d or domain.endswith("." + d) for d in domains)


def score(subject, body):
    scores = Counter()
    for cat, rules in _RULES.items():
        for weight, rx in rules:
            if rx.search(subject):
                scores[cat] += weight * 2
            if rx.search(body):
                scores[cat] += weight
    return scores


def classify(m, contacts=frozenset()):
    """Return (category, confidence, reason). confidence is 'high' or 'low'."""
    labels = [l.strip().lower() for l in m["labels"].split(",")]
    domain, name = m["domain"], m["from_name"].lower()

    if "sent" in labels:
        return "Sent", "high", "Gmail 'Sent' label"
    if m["from_addr"] in contacts or domain in contacts:
        return "Personal", "high", "sender is in contacts list"

    is_platform = _domain_in(domain, C.PLATFORM_DOMAINS)
    claims_platform = any(p in name for p in C.PLATFORM_NAMES)
    if claims_platform and not is_platform:
        return "Possible Scam", "high", f"sender name '{m['from_name']}' but domain is {domain or 'unknown'}"
    if "spam" in labels:
        return "Possible Scam", "high", "Gmail marked it as spam"
    if is_platform:
        return "Social Media Notifications", "high", f"from {domain}"
    if _domain_in(domain, C.LICENSING_DOMAINS):
        return "Video Licensing & Rights", "high", f"from licensing company {domain}"

    scores = score(m["subject"], m["body"])
    if m["bulk"]:
        scores["Newsletters & Promotions"] += 4
    if "category promotions" in labels or "category updates" in labels:
        scores["Newsletters & Promotions"] += 3
    if "category social" in labels:
        scores["Social Media Notifications"] += 3

    if not scores:
        return "Needs Review", "low", "no matching rules"
    ranked = scores.most_common(2)
    best, top = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    if top < C.MIN_SCORE:
        return "Needs Review", "low", f"weak match ({best}, score {top})"
    confidence = "high" if top >= 6 and top >= runner_up * 2 else "low"
    return best, confidence, f"keyword score {top}" + (f" (next: {ranked[1][0]} {runner_up})" if runner_up else "")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

FIELDS = ["id", "date", "category", "confidence", "from_name", "from_addr", "subject", "reason", "preview"]


def safe_filename(name):
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") + ".mbox"


def load_contacts(path):
    if not path:
        return frozenset()
    with open(path, encoding="utf-8-sig") as f:
        return frozenset(line.strip().lower() for line in f if line.strip() and not line.startswith("#"))


def load_ai_results(path):
    """Read ai_sort.py output: {message id: (category, confidence, reason)}."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {
            int(r["id"]): (r["category"], "ai", "Claude: " + r["reason"])
            for r in csv.DictReader(f)
            if r["category"] in C.CATEGORIES
        }


def write_summary(out_dir, counts, total, elapsed):
    lines = [f"Sorted {total:,} emails in {elapsed:.0f}s", ""]
    for cat in C.CATEGORIES:
        if counts[cat]:
            star = "  *" if cat in C.PRIORITY_CATEGORIES else ""
            lines.append(f"{counts[cat]:>9,}  {cat}{star}")
            lines.append(f"           {C.DESCRIPTIONS[cat]}")
    lines += ["", "* = priority: see priority.csv"]
    text = "\n".join(lines) + "\n"
    with open(os.path.join(out_dir, "summary.txt"), "w", encoding="utf-8") as f:
        f.write(text)
    return text


def write_priority(out_dir, rows):
    rows = sorted(rows, key=lambda r: r["date"], reverse=True)
    with open(os.path.join(out_dir, "priority.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def run(source, out, contacts=frozenset(), ai=None, split=True, progress=None):
    """Sort every email in `source` into `out`. Returns (counts, summary_text).

    progress, if given, is called with the running count every 1,000 emails.
    """
    ai = ai or {}
    os.makedirs(out, exist_ok=True)
    split_dir = os.path.join(out, "by_category")
    boxes = {}
    if split:
        os.makedirs(split_dir, exist_ok=True)

    counts = Counter()
    priority = []
    reply_items = []
    start = time.time()
    # utf-8-sig so Excel shows names and emoji correctly when double-clicked
    with open(os.path.join(out, "all_emails.csv"), "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for n, raw in iter_messages(source):
            try:
                m = parse(raw)
                cat, conf, reason = classify(m, contacts)
                if n in ai:
                    cat, conf, reason = ai[n]
            except Exception as e:  # never let one broken email stop the run
                m = {"date": "", "from_name": "", "from_addr": "", "subject": "", "body": ""}
                cat, conf, reason = "Needs Review", "low", f"could not parse: {e}"
            row = {
                "id": n, "date": m["date"], "category": cat, "confidence": conf,
                "from_name": m["from_name"], "from_addr": m["from_addr"],
                "subject": m["subject"], "reason": reason, "preview": m["body"][:200],
            }
            writer.writerow(row)
            counts[cat] += 1
            if cat in C.PRIORITY_CATEGORIES:
                priority.append(row)
            if cat in replies.PAGE_CATEGORIES:
                reply_items.append({**row, "reply_to": m.get("reply_to", ""), "snippet": m["body"][:600]})
            if split:
                if cat not in boxes:
                    boxes[cat] = open(os.path.join(split_dir, safe_filename(cat)), "wb")
                if not raw.startswith(b"From "):
                    raw = b"From MAILER-DAEMON Thu Jan  1 00:00:00 1970\n" + raw
                boxes[cat].write(raw if raw.endswith(b"\n") else raw + b"\n")
            if progress and n % 1000 == 0:
                progress(n)

    for fh in boxes.values():
        fh.close()
    write_priority(out, priority)
    replies.write_page(out, reply_items)
    summary = write_summary(out, counts, sum(counts.values()), time.time() - start)
    return counts, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="Takeout .zip or .mbox file, or a folder of .eml files")
    ap.add_argument("--out", default="sorted_emails", help="output folder (default: sorted_emails)")
    ap.add_argument("--contacts", help="text file of known email addresses/domains, one per line -> 'Personal'")
    ap.add_argument("--no-split", action="store_true", help="skip writing per-category .mbox files")
    ap.add_argument("--ai-results", help="CSV from ai_sort.py to apply (default: <out>/ai_results.csv if it exists)")
    args = ap.parse_args(argv)

    if not os.path.exists(args.source):
        sys.exit(f"Can't find {args.source}")
    ai_path = args.ai_results or os.path.join(args.out, "ai_results.csv")
    ai = load_ai_results(ai_path)
    if ai:
        print(f"Applying {len(ai):,} Claude decisions from {ai_path}", file=sys.stderr)

    def progress(n):
        if n % 10000 == 0:
            print(f"  ...{n:,} emails sorted", file=sys.stderr)

    counts, summary = run(args.source, args.out, load_contacts(args.contacts), ai,
                          split=not args.no_split, progress=progress)
    print(summary)
    print(f"Results written to {os.path.abspath(args.out)}/")
    if counts["Needs Review"]:
        print(f"Tip: run `python3 ai_sort.py \"{args.source}\" --out {args.out}` to have Claude sort the "
              f"{counts['Needs Review']:,} 'Needs Review' emails.")


if __name__ == "__main__":
    main()
