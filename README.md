# Viral Inbox Sorter

Sorts hundreds of thousands of emails into categories, so a creator whose video
just went viral can find the brand deals, licensing requests and press
inquiries buried under fan mail, notifications and scams.

| Category | What goes in it |
|---|---|
| ⭐ Business & Brand Deals | Sponsorships, paid partnerships, collabs, appearances |
| ⭐ Video Licensing & Rights | Jukin, ViralHog, Storyful, TV shows etc. asking to use the video |
| ⭐ Media & Press | Interview requests, reporters, producers, podcasts |
| ⭐ Management & Agencies | Managers and agencies offering representation |
| Fan Mail | Viewers reacting to the video |
| Possible Scam | Fake "Meta/Facebook" warnings, verification-badge offers, money requests |
| Social Media Notifications | Real notifications from Facebook, Instagram, TikTok… |
| Newsletters & Promotions | Marketing and bulk mail |
| Personal | Addresses you list in a contacts file |
| Sent | Emails you sent |
| Needs Review | Couldn't be sorted confidently |

⭐ = priority: these are collected into `priority.csv`, newest first.

## Step 1: Download your email (Gmail)

1. Go to <https://takeout.google.com> and sign in to the Gmail account.
2. Click **Deselect all**, then scroll down and tick **Mail** only.
3. Click **Next step** → **Create export**. Google emails you a download link
   (for a big inbox this can take hours, even a day).
4. Download and unzip it. You'll get a file like
   `Takeout/Mail/All mail Including Spam and Trash.mbox`.

Using Outlook, Yahoo or something else? Export your mail as `.mbox` or as a
folder of `.eml` files. Either one works.

## Step 2: Sort it (free and private)

You need Python 3.8 or newer. No other installs are needed for this step.

```bash
python3 sort_emails.py "Takeout/Mail/All mail Including Spam and Trash.mbox"
```

This runs entirely on your own computer. Nothing is sent anywhere, and it
handles about 1,000 emails a second. Results land in `sorted_emails/`:

- **`priority.csv`**: start here. Opens in Excel, Google Sheets or Numbers.
- **`all_emails.csv`**: every email with its category and the reason it was put there.
- **`summary.txt`**: how many emails landed in each category.
- **`by_category/*.mbox`**: one mailbox per category. You can open these in
  [Thunderbird](https://www.thunderbird.net) (with the ImportExportTools NG add-on)
  to read and reply to them.

Optional: to route friends and family to **Personal**, create a
`contacts.txt` with one email address (or whole domain) per line:

```bash
python3 sort_emails.py mail.mbox --contacts contacts.txt
```

## Step 3 (optional): Let Claude sort the leftovers

Emails the rules can't place go to **Needs Review**. Claude can read those and
sort them. This needs an Anthropic API key from
<https://console.anthropic.com> and costs money, so the script shows an
estimate and asks before it sends anything.

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...
python3 ai_sort.py "Takeout/Mail/All mail Including Spam and Trash.mbox"
python3 sort_emails.py "Takeout/Mail/All mail Including Spam and Trash.mbox"   # re-run to apply Claude's answers
```

- It uses the Batch API (half price). Results usually arrive within an hour.
  If you close the window, just run the command again and it picks up where it left off.
- `--scope low` also re-checks the rules' low-confidence guesses, and `--scope all` sends everything.
- `--model` picks a different Claude model. The default is `claude-opus-5`, and
  `claude-haiku-4-5` is much cheaper for very large runs.
- **Privacy:** this step sends each selected email's sender, subject and the
  first 2,000 characters of the body to Anthropic's API.

Always use the same email file for all three commands. Claude's answers are
matched to emails by their position in that file.

## Tuning the rules

All keywords, sender domains and categories live in
[`categories.py`](categories.py). For example, to catch a new licensing
company, add its domain to `LICENSING_DOMAINS`. To change what counts as a
brand deal, edit the keywords under `"Business & Brand Deals"`. Then re-run
`sort_emails.py`.

## A word on scams

Viral creators get flooded with fake "Meta Support" emails threatening to
disable the page, and with offers of a "blue verification badge". Real
Facebook emails come from `facebookmail.com`. Anything in **Possible Scam**:
don't click links, don't log in, and don't pay anything.

## Tests

```bash
python3 -m unittest discover -s tests
```
