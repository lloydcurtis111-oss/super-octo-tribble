#!/usr/bin/env python3
"""
Have Claude sort the emails the keyword rules couldn't.

Run sort_emails.py first, then:

    export ANTHROPIC_API_KEY=sk-ant-...
    python3 ai_sort.py "All mail Including Spam and Trash.mbox"
    python3 sort_emails.py "All mail Including Spam and Trash.mbox"   # re-run to apply

Uses the Message Batches API (half price, results usually within an hour).
It shows a cost estimate and asks before sending anything. If the script is
interrupted, run it again -- it picks up the batches it already submitted
from <out>/ai_batches.json instead of paying twice.

Privacy note: this sends each selected email's sender, subject and the first
part of its body to Anthropic's API. The keyword step (sort_emails.py) never
sends anything anywhere.
"""

import argparse
import csv
import json
import os
import sys
import time

import categories as C
from sort_emails import iter_messages, parse

DEFAULT_MODEL = "claude-opus-5"
AI_BODY_CHARS = 2000   # characters of body sent per email (keeps cost predictable)
BATCH_SIZE = 50_000    # API limit is 100k requests / 256 MB per batch
# Batch pricing for claude-opus-5 ($ per million tokens). Estimate only.
PRICE_IN, PRICE_OUT = 2.50, 12.50
EST_OUTPUT_TOKENS = 150

AI_CATEGORIES = [c for c in C.CATEGORIES if c not in ("Sent", "Needs Review")] + ["Needs Review"]

SYSTEM = (
    "You sort email for Anthony Taylor, whose Facebook video with his son went viral "
    "(52 million views). His inbox is flooded. Put each email in exactly one category:\n\n"
    + "\n".join(f"- {c}: {C.DESCRIPTIONS[c]}" for c in AI_CATEGORIES)
    + "\n\nGuidance:\n"
    "- Anything pressuring him to click a link, log in, pay, or 'verify' his page to avoid "
    "losing it is a Possible Scam, even if it looks like it's from Facebook/Meta.\n"
    "- Legitimate offers that involve money for Anthony (sponsorships, licensing fees, paid "
    "appearances) are high priority; vague 'opportunities' asking him to pay up front are scams.\n"
    "- Use Needs Review only when it truly doesn't fit anywhere.\n"
    "- reason: one short sentence a busy person can skim."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": AI_CATEGORIES},
        "priority": {"type": "string", "enum": ["high", "normal", "low"]},
        "reason": {"type": "string"},
    },
    "required": ["category", "priority", "reason"],
    "additionalProperties": False,
}


def email_prompt(m):
    return (
        f"From: {m['from_name']} <{m['from_addr']}>\n"
        f"Date: {m['date']}\n"
        f"Subject: {m['subject']}\n\n"
        f"{m['body'][:AI_BODY_CHARS]}"
    )


def make_request(n, m, model):
    return {
        "custom_id": f"msg-{n}",
        "params": {
            "model": model,
            "max_tokens": 2000,
            "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": email_prompt(m)}],
            "output_config": {
                "effort": "low",
                "format": {"type": "json_schema", "schema": SCHEMA},
            },
        },
    }


def select_ids(out_dir, scope):
    path = os.path.join(out_dir, "all_emails.csv")
    if not os.path.exists(path):
        sys.exit(f"{path} not found -- run sort_emails.py first.")
    ids = set()
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["category"] in ("Sent", "Personal"):
                continue
            if (scope == "all"
                    or r["category"] == "Needs Review"
                    or (scope == "low" and r["confidence"] == "low")):
                ids.add(int(r["id"]))
    return ids


def build_requests(source, ids, model):
    reqs = []
    for n, raw in iter_messages(source):
        if n in ids:
            try:
                reqs.append(make_request(n, parse(raw), model))
            except Exception as e:
                print(f"  skipping email {n}: {e}", file=sys.stderr)
    return reqs


def estimate_cost(reqs):
    chars = len(SYSTEM) * len(reqs) + sum(len(r["params"]["messages"][0]["content"]) for r in reqs)
    in_tok = chars / 4
    out_tok = EST_OUTPUT_TOKENS * len(reqs)
    return (in_tok * PRICE_IN + out_tok * PRICE_OUT) / 1_000_000


def submit(client, reqs, state_path):
    batch_ids = []
    for i in range(0, len(reqs), BATCH_SIZE):
        chunk = reqs[i:i + BATCH_SIZE]
        batch = client.messages.batches.create(requests=chunk)
        batch_ids.append(batch.id)
        with open(state_path, "w") as f:  # save after each so a crash never double-bills
            json.dump({"batch_ids": batch_ids}, f)
        print(f"  submitted batch {batch.id} ({len(chunk):,} emails)")
    return batch_ids


def wait(client, batch_ids):
    while True:
        batches = [client.messages.batches.retrieve(b) for b in batch_ids]
        pending = [b for b in batches if b.processing_status != "ended"]
        done = sum(b.request_counts.succeeded + b.request_counts.errored for b in batches)
        if not pending:
            return
        print(f"  waiting on Claude... {done:,} done so far (checking again in 60s)")
        time.sleep(60)


def collect(client, batch_ids, results_path):
    rows, failed = [], 0
    for bid in batch_ids:
        for res in client.messages.batches.results(bid):
            n = int(res.custom_id.split("-", 1)[1])
            if res.result.type != "succeeded":
                failed += 1
                continue
            msg = res.result.message
            text = next((b.text for b in msg.content if b.type == "text"), "")
            if msg.stop_reason != "end_turn" or not text:
                failed += 1
                continue
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                failed += 1
                continue
            rows.append({"id": n, **data})
    rows.sort(key=lambda r: r["id"])
    with open(results_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "category", "priority", "reason"])
        w.writeheader()
        w.writerows(rows)
    return rows, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", help="the same .mbox file / .eml folder you gave sort_emails.py")
    ap.add_argument("--out", default="sorted_emails", help="output folder used by sort_emails.py")
    ap.add_argument("--scope", choices=["review", "low", "all"], default="review",
                    help="review = only 'Needs Review' (default); low = also low-confidence guesses; all = everything")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"Claude model (default: {DEFAULT_MODEL})")
    ap.add_argument("--yes", action="store_true", help="skip the cost confirmation prompt")
    args = ap.parse_args(argv)

    import anthropic  # imported here so sort_emails.py works without it installed
    client = anthropic.Anthropic()

    state_path = os.path.join(args.out, "ai_batches.json")
    results_path = os.path.join(args.out, "ai_results.csv")

    if os.path.exists(state_path):
        with open(state_path) as f:
            batch_ids = json.load(f)["batch_ids"]
        print(f"Resuming {len(batch_ids)} batch(es) submitted earlier (delete {state_path} to start over).")
    else:
        ids = select_ids(args.out, args.scope)
        if not ids:
            print("Nothing to send -- every email already has a category.")
            return
        print(f"Preparing {len(ids):,} emails for Claude...")
        reqs = build_requests(args.source, ids, args.model)
        cost = estimate_cost(reqs)
        print(f"Estimated cost: about ${cost:,.2f} with {args.model} (Batch API, half price). "
              "Rough estimate -- actual cost may differ.")
        if not args.yes and input("Send to Claude? Type 'yes' to continue: ").strip().lower() != "yes":
            print("Cancelled. Nothing was sent.")
            return
        batch_ids = submit(client, reqs, state_path)

    wait(client, batch_ids)
    rows, failed = collect(client, batch_ids, results_path)
    print(f"\nClaude sorted {len(rows):,} emails -> {results_path}")
    if failed:
        print(f"{failed:,} could not be sorted and will stay in 'Needs Review'.")
    print(f"Now re-run: python3 sort_emails.py \"{args.source}\" --out {args.out}")


if __name__ == "__main__":
    main()
