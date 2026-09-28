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

## How to use it (nothing to install)

Works on a **Chromebook**, Windows or Mac. All you need is the Chrome browser.

### 1. Download your email from Google
1. Go to <https://takeout.google.com> and sign in to the Gmail account.
2. Click **Deselect all**, then scroll down and tick **Mail** only.
3. Click **Next step** and then **Create export**.
4. Wait for Google's email saying the export is ready. For a big inbox this
   can take several hours or up to a day. Download the file it links to (a
   `.zip`). **Don't unzip it**, the sorter reads the zip directly.

### 2. Get the Email Sorter
Download the single file **`Email Sorter.html`** from this project. On GitHub,
open the file and click the **Download raw file** button (the arrow pointing
down, at the top right of the file).

### 3. Sort
1. Open your **Downloads** folder (on a Chromebook: the **Files** app) and
   double-click **Email Sorter.html**. It opens in Chrome.
2. Click **Choose file...** and pick the Google Takeout `.zip` from step 1.
3. Click **Sort my emails**. Keep the tab open until it says **Done**.

Everything happens inside that page. Your emails are never uploaded anywhere,
and the page works without an internet connection.

When it's done you'll see how many emails landed in each category, plus:
- **Save reply page for later**: saves the reply page (step 4) to your
  Downloads folder, so you can come back to it without sorting again.
- **Important emails / All emails (spreadsheet)**: lists that open in
  Google Sheets or Excel.

### 4. Reply to the important emails
When sorting finishes, the **Important Emails** list appears under the results.
It lists every brand deal, licensing, press and management email, plus the
newest fan mail. Each one comes with a ready-made reply.

1. Read the email and edit the reply in the box however you like.
2. Click **Open in Gmail**. A new Gmail message opens with the address,
   subject and reply already filled in.
3. Check it and press **Send**. Nothing is ever sent automatically.
4. Tick **Replied** so the email drops off your list. The page remembers
   your edits and ticks, even after you close it.

Tip: if you have more than one Gmail account, type the right address into
the "Your Gmail address" box at the top so replies come from that account.

Type the name to sign replies with in the **Sign replies as** box before
sorting. To change the ready-made wording itself, edit [`replies.py`](replies.py)
and run `python3 build_web.py`.

## Desktop app for Windows and Mac (older option)

The browser version above is easier. This Python app does the same sorting,
plus one mailbox file per category, and writes its results into a **Sorted
Emails** folder next to the email file.

#### 1. Download the email from Google
1. On a computer, go to <https://takeout.google.com> and sign in to the Gmail account.
2. Click **Deselect all**, then scroll down and tick **Mail** only.
3. Click **Next step** and then **Create export**.
4. Wait for Google's email saying the export is ready. For a big inbox this
   can take several hours or up to a day. Download the file it links to (a
   `.zip`). **Don't unzip it**, the sorter reads the zip directly.

#### 2. Install Python (one time only, free)
- Go to <https://www.python.org/downloads/> and click the big yellow Download button.
- **Windows:** run the installer. On the first screen, **tick "Add python.exe to PATH"**
  at the bottom, then click **Install Now**.
- **Mac:** open the downloaded file and click Continue until it's done.

#### 3. Get this Email Sorter
On this project's GitHub page, click the green **Code** button, then
**Download ZIP**. Unzip it (double-click it) and put the folder somewhere easy
to find, like the Desktop.

#### 4. Sort!
1. Open the Email Sorter folder and double-click:
   - **Windows:** `Start (Windows)`. Leave the black window that opens
     alongside it open. If anything goes wrong, the error shows up there.
   - **Mac:** `Start (Mac)`. The first time, macOS may block it because it's
     from an "unidentified developer". If it does:
     1. Click **Done** (or **OK**) on the warning.
     2. Open **System Settings**, go to **Privacy & Security**, and scroll to the bottom.
     3. Click **Open Anyway** next to "Start (Mac)", then confirm with **Open Anyway** again.

     On older Macs you can instead **right-click** the file, choose **Open**, and click **Open**.
2. Click **Choose file...** and pick the Google Takeout `.zip` from step 1.
3. Click **Sort my emails**. A big inbox takes a few minutes.
4. When it's done, the **Important Emails** reply page opens in your web browser.
   Everything is saved in a **Sorted Emails** folder next to the file you picked.

Everything happens on your own computer. Your emails are never uploaded anywhere.

#### What you get in the "Sorted Emails" folder
- **`replies.html`**: the Important Emails page above. Double-click it to open it again later.
- **`priority.csv`**: ⭐ start here. The brand deals, licensing, press and
  management emails, newest first.
- **`all_emails.csv`**: every email, with its category and why it was put there.
- **`summary.txt`**: how many emails are in each category.
- **`by_category`**: one mailbox file per category. To read and reply to
  them, open these in [Thunderbird](https://www.thunderbird.net) (free) with
  the ImportExportTools NG add-on.

Search for an email in Gmail by its subject to reply to it from your normal inbox.

## For the technical person: command line

Using Outlook, Yahoo or another provider? Export the mail as `.mbox` or as a
folder of `.eml` files, then run:

```bash
python3 sort_emails.py "takeout-001.zip"        # a .zip, .mbox or folder of .eml files
python3 sort_emails.py mail.mbox --out results   # choose where results go
```

It handles roughly 1,000 emails a second. To route friends and family to
**Personal**, create a `contacts.txt` with one email address (or whole domain)
per line:

```bash
python3 sort_emails.py mail.mbox --contacts contacts.txt
```

## Optional: let Claude sort the leftovers (technical, costs money)

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
brand deal, edit the keywords under `"Business & Brand Deals"`. Then run
`python3 build_web.py` to rebuild `Email Sorter.html`.

## A word on scams

Viral creators get flooded with fake "Meta Support" emails threatening to
disable the page, and with offers of a "blue verification badge". Real
Facebook emails come from `facebookmail.com`. Anything in **Possible Scam**:
don't click links, don't log in, and don't pay anything.

## Tests

```bash
python3 -m unittest discover -s tests
```

The browser-version tests run the page's code under Node.js and check that it
sorts every email exactly like the Python version (skipped if Node is missing).
