"""
Ready-made replies and the "Reply to emails" page.

After sorting, this writes replies.html: every important email with a draft
reply you can edit, plus an "Open in Gmail" button that opens a new Gmail
message with the reply filled in. Nothing is ever sent automatically --
you read it, change what you like, and press Send yourself.

Edit the TEMPLATES below to change the wording. {name} becomes the sender's
first name, and {signature} becomes SIGNATURE.
"""

import json
import os
import re
from html import escape

SIGNATURE = "Anthony Taylor"

TEMPLATES = {
    "Business & Brand Deals": """Hi {name},

Thanks so much for reaching out! I'm interested in hearing more.

Could you send over the details?
- What you'd like me to create or post, and on which platforms
- Timeline and deadlines
- Budget / compensation
- How long you'd want to use the content, and where

Looking forward to it.

{signature}""",

    "Video Licensing & Rights": """Hi {name},

Thanks for your interest in the video.

Before I agree to anything, could you send the full terms in writing?
- Exclusive or non-exclusive
- Upfront fee and/or revenue share (and the percentage)
- Where it will be used, and for how long

I'm not signing any exclusive agreements at this time, and I'll have the terms reviewed before signing.

{signature}""",

    "Media & Press": """Hi {name},

Thanks for reaching out, I'd be happy to talk.

Could you let me know:
- The outlet or show, and when it would run
- Your deadline
- Whether it's by phone, video, or in person

{signature}""",

    "Management & Agencies": """Hi {name},

Thanks for reaching out.

Could you send some information about your company?
- Creators you currently represent
- Your commission and contract length
- What you would do for me in the first 90 days

{signature}""",

    "Fan Mail": """Hi {name},

Thank you so much for your kind message. It really means a lot to me and my son!

{signature}""",
}

# Categories that show up on the reply page, with how many to include at most.
# Fan mail can run into the tens of thousands, so only the newest are shown.
PAGE_CATEGORIES = {
    "Business & Brand Deals": None,
    "Video Licensing & Rights": None,
    "Media & Press": None,
    "Management & Agencies": None,
    "Fan Mail": 300,
}


# Words that mean the sender is a company or department, not a person.
GENERIC_NAME_WORDS = {
    "the", "team", "info", "no", "noreply", "support", "rights", "licensing", "media", "news",
    "desk", "partnerships", "partners", "marketing", "sales", "hello", "hi", "admin", "office",
    "customer", "service", "notifications", "editorial", "booking", "inc", "llc", "ltd",
}


def first_name(display_name):
    """'Sara Lee' -> 'Sara'; falls back to 'there' for companies and odd names."""
    words = re.findall(r"[A-Za-z'\-]+", (display_name or "").replace('"', ""))
    if not words or any(w.lower() in GENERIC_NAME_WORDS for w in words):
        return "there"
    word = words[0]
    if re.fullmatch(r"[A-Za-z][A-Za-z'\-]{1,20}", word):
        return word.capitalize()
    return "there"


def draft_reply(category, display_name, signature=SIGNATURE):
    template = TEMPLATES.get(category)
    if not template:
        return ""
    return template.format(name=first_name(display_name), signature=signature)


def reply_subject(subject):
    subject = subject or ""
    return subject if re.match(r"(?i)re:", subject) else f"Re: {subject}".strip()


def collect(items):
    """Pick which emails go on the page: all priority mail + newest fan mail."""
    by_cat = {c: [] for c in PAGE_CATEGORIES}
    for it in items:
        if it["category"] in by_cat:
            by_cat[it["category"]].append(it)
    chosen = []
    for cat, limit in PAGE_CATEGORIES.items():
        rows = sorted(by_cat[cat], key=lambda r: r["date"], reverse=True)
        chosen += rows[:limit] if limit else rows
    return chosen


def write_page(out_dir, items):
    """Write replies.html into out_dir and return its path."""
    emails = [
        {
            "id": it["id"],
            "category": it["category"],
            "date": it["date"],
            "from": it["from_name"] or it["from_addr"],
            "to": it.get("reply_to") or it["from_addr"],
            "subject": it["subject"],
            "reply_subject": reply_subject(it["subject"]),
            "preview": it.get("snippet", ""),
            "draft": draft_reply(it["category"], it["from_name"]),
        }
        for it in collect(items)
    ]
    data = json.dumps(emails, ensure_ascii=False).replace("</", "<\\/")
    tabs = "".join(
        f'<button class="tab" data-cat="{escape(c)}">{escape(c)}</button>' for c in PAGE_CATEGORIES
    )
    path = os.path.join(out_dir, "replies.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(PAGE.replace("{{TABS}}", tabs).replace("{{DATA}}", data))
    return path


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Important Emails</title>
<style>
  :root { --bg:#f6f6f4; --card:#fff; --text:#1c1c1c; --muted:#6b6b6b; --line:#e2e2de;
          --accent:#1a73e8; --accent-text:#fff; --done:#e9f5ec; --warn:#fff6e0; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#161616; --card:#222; --text:#eee; --muted:#a0a0a0; --line:#353535;
            --accent:#8ab4f8; --accent-text:#10213d; --done:#1d2f22; --warn:#3a2f14; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:16px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  main { max-width: 860px; margin: 0 auto; padding: 24px 16px 64px; }
  h1 { margin: 0 0 4px; font-size: 28px; }
  .muted { color: var(--muted); }
  .note { background: var(--warn); border-radius: 10px; padding: 12px 14px; margin: 16px 0; font-size: 15px; }
  .bar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin: 16px 0; }
  .tab { border:1px solid var(--line); background:var(--card); color:var(--text); border-radius:999px;
         padding:6px 14px; font-size:14px; cursor:pointer; }
  .tab.on { background: var(--accent); color: var(--accent-text); border-color: var(--accent); }
  input[type=search], input[type=email] { border:1px solid var(--line); background:var(--card); color:var(--text);
         border-radius:8px; padding:8px 10px; font-size:15px; }
  input[type=search] { flex: 1 1 220px; }
  label.hide { font-size:14px; display:flex; gap:6px; align-items:center; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; margin:12px 0; }
  .card.done { background: var(--done); }
  .card.done .body { display:none; }
  .head { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; }
  .subj { font-weight:600; font-size:17px; overflow-wrap:anywhere; }
  .meta { font-size:14px; color:var(--muted); overflow-wrap:anywhere; }
  .preview { font-size:14px; color:var(--muted); margin:8px 0 12px; white-space:pre-wrap; overflow-wrap:anywhere; }
  textarea { width:100%; min-height:120px; resize:vertical; border:1px solid var(--line); border-radius:8px; padding:10px;
             background:var(--bg); color:var(--text); font-size:15px; line-height:1.45; font-family:inherit; }
  .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:10px; align-items:center; }
  .btn { background:var(--accent); color:var(--accent-text); border:0; border-radius:8px; padding:9px 16px;
         font-size:15px; font-weight:600; cursor:pointer; text-decoration:none; }
  .btn.secondary { background:transparent; color:var(--text); border:1px solid var(--line); font-weight:500; }
  .more { text-align:center; margin: 20px 0; }
  .empty { text-align:center; padding: 40px 0; }
</style>
</head>
<body>
<main>
  <h1>Important Emails</h1>
  <div class="muted" id="count"></div>

  <div class="note">
    <b>How this works:</b> read the email, edit the reply in the box, then click <b>Open in Gmail</b>.
    Gmail opens with the reply ready to go. Check it and press Send yourself. Nothing is sent automatically.
    <br><b>Never</b> agree to exclusive rights, send passwords, or pay anyone upfront over email.
  </div>

  <div class="bar">
    <label for="acct" class="muted" style="font-size:14px">Your Gmail address (optional):</label>
    <input type="email" id="acct" placeholder="you@gmail.com" size="26">
  </div>
  <div class="bar" id="tabs"><button class="tab on" data-cat="">All</button>{{TABS}}</div>
  <div class="bar">
    <input type="search" id="q" placeholder="Search by name, company or subject">
    <label class="hide"><input type="checkbox" id="hideDone" checked> Hide emails I've replied to</label>
  </div>

  <div id="list"></div>
  <div class="more"><button class="btn secondary" id="more" hidden>Show more</button></div>
</main>

<script type="application/json" id="data">{{DATA}}</script>
<script>
const EMAILS = JSON.parse(document.getElementById('data').textContent);
const PAGE = 40;
const store = {
  get(k, d) { try { const v = localStorage.getItem('replies:' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem('replies:' + k, JSON.stringify(v)); } catch (e) {} },
};
let cat = '', shown = PAGE;
const done = new Set(store.get('done', []));
const drafts = store.get('drafts', {});
const $ = s => document.querySelector(s);
const acct = $('#acct');
acct.value = store.get('acct', '');
acct.oninput = () => store.set('acct', acct.value.trim());

function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

function gmailUrl(e, body) {
  const p = new URLSearchParams({ view: 'cm', fs: '1', to: e.to, su: e.reply_subject, body });
  if (acct.value.trim()) p.set('authuser', acct.value.trim());
  return 'https://mail.google.com/mail/?' + p.toString();
}

function matches(e) {
  if (cat && e.category !== cat) return false;
  if ($('#hideDone').checked && done.has(e.id)) return false;
  const q = $('#q').value.trim().toLowerCase();
  return !q || (e.from + ' ' + e.to + ' ' + e.subject + ' ' + e.preview).toLowerCase().includes(q);
}

function render() {
  const list = EMAILS.filter(matches);
  const todo = EMAILS.filter(e => !done.has(e.id)).length;
  $('#count').textContent = `${EMAILS.length.toLocaleString()} emails · ${todo.toLocaleString()} still to reply to`;
  const box = $('#list');
  box.innerHTML = list.length ? '' : '<div class="empty muted">Nothing here.</div>';
  for (const e of list.slice(0, shown)) {
    const card = document.createElement('div');
    card.className = 'card' + (done.has(e.id) ? ' done' : '');
    card.innerHTML = `
      <div class="head">
        <div><div class="subj">${esc(e.subject) || '(no subject)'}</div>
        <div class="meta">${esc(e.from)} &lt;${esc(e.to)}&gt;</div></div>
        <div class="meta">${esc(e.category)}<br>${esc(e.date)}</div>
      </div>
      <div class="body">
        <div class="preview">${esc(e.preview)}</div>
        <textarea aria-label="Reply"></textarea>
      </div>
      <div class="actions">
        <a class="btn" target="_blank" rel="noopener">Open in Gmail</a>
        <button class="btn secondary copy">Copy reply</button>
        <label class="hide"><input type="checkbox" class="mark"> Replied</label>
      </div>`;
    const ta = card.querySelector('textarea');
    ta.value = drafts[e.id] ?? e.draft;
    const fit = () => { ta.style.height = 'auto'; ta.style.height = (ta.scrollHeight + 4) + 'px'; };
    ta.oninput = () => { fit(); drafts[e.id] = ta.value; store.set('drafts', drafts); };
    const link = card.querySelector('a.btn');
    link.onmousedown = link.onfocus = () => { link.href = gmailUrl(e, ta.value); };
    link.href = gmailUrl(e, ta.value);
    card.querySelector('.copy').onclick = async (ev) => {
      try { await navigator.clipboard.writeText(ta.value); ev.target.textContent = 'Copied!'; }
      catch (err) { ta.select(); document.execCommand('copy'); ev.target.textContent = 'Copied!'; }
    };
    const mark = card.querySelector('.mark');
    mark.checked = done.has(e.id);
    mark.onchange = () => {
      mark.checked ? done.add(e.id) : done.delete(e.id);
      store.set('done', [...done]);
      render();
    };
    box.appendChild(card);
    fit();
  }
  $('#more').hidden = list.length <= shown;
}

document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
  t.classList.add('on'); cat = t.dataset.cat; shown = PAGE; render();
});
$('#q').oninput = () => { shown = PAGE; render(); };
$('#hideDone').onchange = render;
$('#more').onclick = () => { shown += PAGE; render(); };
render();
</script>
</body>
</html>
"""
