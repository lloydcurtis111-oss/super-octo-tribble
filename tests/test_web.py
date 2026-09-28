"""
Tests for the in-browser version ("Email Sorter.html").

The browser code is run under Node and must sort every email exactly the same
way as the Python sorter. Skipped if Node isn't installed.
"""

import csv
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from email.message import EmailMessage
from email.utils import formataddr

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import build_web  # noqa: E402
import sort_emails as S  # noqa: E402
from test_sorter import SAMPLES  # noqa: E402

NODE = shutil.which("node")


def mbox_entry(msg, crlf=False):
    raw = msg.as_bytes() if isinstance(msg, EmailMessage) else msg
    raw = raw.replace(b"\r\n", b"\n")
    raw = raw.replace(b"\nFrom ", b"\n>From ")  # mbox escaping, as Gmail's export does
    if crlf:
        raw = raw.replace(b"\n", b"\r\n")
    nl = b"\r\n" if crlf else b"\n"
    return b"From MAILER-DAEMON Mon Sep  1 10:00:00 2026" + nl + raw + nl


def tricky_messages():
    """Real-world shapes: encoded headers, multipart, base64, HTML-only, attachments."""
    out = []

    m = EmailMessage()
    m["From"] = formataddr(("José Álvarez", "jose@marca.es"))
    m["Subject"] = "Colaboración pagada — paid partnership 🎉"
    m["Date"] = "Tue, 2 Sep 2026 08:30:00 +0000"
    m["Reply-To"] = "deals@marca.es"
    m.set_content("Hola! We'd love a paid partnership. What are your rates? Budget is ready.", charset="utf-8",
                  cte="base64")
    m.add_alternative("<p>Hola! We'd <b>love</b> a paid partnership.</p>", subtype="html")
    m.add_attachment(b"%PDF-1.4 fake" * 2000, maintype="application", subtype="pdf", filename="brief.pdf")
    out.append(m)

    m = EmailMessage()
    m["From"] = "=?utf-8?Q?Channel_7_News_Desk?= <producer@ch7news.com>"
    m["Subject"] = "=?utf-8?B?SW50ZXJ2aWV3IHJlcXVlc3Q=?= for tonight"
    m["Date"] = "Wed, 3 Sep 2026 17:00:00 +0000"
    m.set_content("<html><body><h1>Hi!</h1><p>I&#39;m a reporter &amp; producer at Channel 7. "
                  "Could we do an interview request for our show?</p><style>p{}</style></body></html>",
                  subtype="html", cte="quoted-printable")
    out.append(m)

    m = EmailMessage()
    m["From"] = "Grandma Rose <rose.fan@yahoo.com>"
    m["Subject"] = "Saw your video!!"
    m["Date"] = "Thu, 4 Sep 2026 12:00:00 +0000"
    m["X-Gmail-Labels"] = "Inbox,Opened,Category Personal"
    m.set_content("I saw your video with your son and it touched my heart. God bless you! "
                  "From the kitchen table,\nRose\n\nFrom now on I'm your biggest fan.", cte="quoted-printable")
    out.append(m)

    m = EmailMessage()
    m["From"] = '"Facebook Copyright Team" <alerts@fb-copyright-help.net>'
    m["Subject"] = "Final warning: your page will be disabled"
    m["Date"] = "Fri, 5 Sep 2026 01:00:00 +0000"
    m.set_content("Appeal within 24 hours or your page will be deleted.")
    out.append(m)

    m = EmailMessage()
    m["From"] = "Deals <news@shop.example>"
    m["Subject"] = "Weekend sale"
    m["Date"] = "Sat, 6 Sep 2026 09:00:00 +0000"
    m["List-Unsubscribe"] = "<mailto:unsub@shop.example>"
    m["X-Gmail-Labels"] = "Category Promotions"
    m.set_content("Shop now, 50% off. Unsubscribe here.")
    out.append(m)

    m = EmailMessage()
    m["From"] = "no-date@example.com"
    m["Subject"] = "no date, no name"
    m.set_content("hello")
    out.append(m)
    return out


def build_mbox(crlf=False):
    body = b"".join(raw.encode() for _, raw in SAMPLES)
    body += b"".join(mbox_entry(m, crlf=crlf) for m in tricky_messages())
    return body


@unittest.skipUnless(NODE, "node is not installed")
class WebParityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rules = os.path.join(self.tmp.name, "rules.json")
        with open(self.rules, "w", encoding="utf-8") as f:
            json.dump(build_web.rules(), f, ensure_ascii=False)

    def tearDown(self):
        self.tmp.cleanup()

    def run_node(self, path):
        env = dict(os.environ, TZ="UTC")
        out = subprocess.run([NODE, os.path.join(HERE, "web_run.js"), self.rules, path],
                             capture_output=True, check=True, env=env, timeout=120)
        return json.loads(out.stdout)

    def run_python(self, path):
        out = os.path.join(self.tmp.name, "py_out")
        S.run(path, out, split=False)
        with open(os.path.join(out, "all_emails.csv"), encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        html = open(os.path.join(out, "replies.html"), encoding="utf-8").read()
        replies = json.loads(html.split('id="data">', 1)[1].split("</script>", 1)[0])
        return rows, replies

    def assert_same(self, path):
        js = self.run_node(path)
        py_rows, py_replies = self.run_python(path)
        js_rows = list(csv.DictReader(io.StringIO(js["csv"].lstrip("﻿"))))
        self.assertEqual(len(js_rows), len(py_rows))
        for p, j in zip(py_rows, js_rows):
            for field in ("id", "category", "confidence", "from_name", "from_addr", "subject", "date", "reason", "preview"):
                self.assertEqual(j[field], p[field], f"email {p['id']} ({p['subject']!r}): {field} differs")
        self.assertEqual(js["replies"], py_replies)
        return js

    def test_mbox_matches_python(self):
        path = os.path.join(self.tmp.name, "mail.mbox")
        with open(path, "wb") as f:
            f.write(build_mbox())
        js = self.assert_same(path)
        self.assertEqual(js["total"], len(SAMPLES) + len(tricky_messages()))
        cats = [r["category"] for r in csv.DictReader(io.StringIO(js["csv"].lstrip("﻿")))]
        self.assertEqual(cats[len(SAMPLES):], [
            "Business & Brand Deals", "Media & Press", "Fan Mail",
            "Possible Scam", "Newsletters & Promotions", "Needs Review",
        ])

    def test_crlf_mbox_matches_python(self):
        path = os.path.join(self.tmp.name, "crlf.mbox")
        with open(path, "wb") as f:
            f.write(build_mbox(crlf=True))
        self.assert_same(path)

    def test_takeout_zip_matches_python(self):
        path = os.path.join(self.tmp.name, "takeout-001.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("Takeout/archive_browser.html", "<html></html>")
            z.writestr("Takeout/Mail/All mail Including Spam and Trash.mbox", build_mbox() * 30)
        js = self.assert_same(path)
        self.assertEqual(js["total"], 30 * (len(SAMPLES) + len(tricky_messages())))

    def test_zip_without_mail(self):
        path = os.path.join(self.tmp.name, "photos.zip")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("Takeout/Photos/a.jpg", "x")
        env = dict(os.environ, TZ="UTC")
        out = subprocess.run([NODE, os.path.join(HERE, "web_run.js"), self.rules, path],
                             capture_output=True, env=env, timeout=60)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn(b"no emails inside", out.stderr)


class BuildTest(unittest.TestCase):
    def test_built_page_is_up_to_date(self):
        """'Email Sorter.html' must be rebuilt after editing the rules or web/ files."""
        with tempfile.TemporaryDirectory() as d:
            fresh = build_web.build(os.path.join(d, "page.html"))
            with open(fresh, encoding="utf-8") as f:
                expected = f.read()
        with open(build_web.OUTPUT, encoding="utf-8") as f:
            self.assertEqual(f.read(), expected, "Run: python3 build_web.py")


if __name__ == "__main__":
    unittest.main()
