import csv
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ai_sort  # noqa: E402
import sort_emails as S  # noqa: E402


def make_email(frm, subject, body, extra_headers=""):
    return (
        f"From MAILER-DAEMON Mon Sep  1 10:00:00 2026\n"
        f"From: {frm}\n"
        f"To: anthony@example.com\n"
        f"Subject: {subject}\n"
        f"Date: Mon, 1 Sep 2026 10:00:00 +0000\n"
        f"{extra_headers}"
        f"Content-Type: text/plain; charset=utf-8\n\n"
        f"{body}\n\n"
    )


SAMPLES = [
    ("Possible Scam", make_email('"Meta Support" <security@meta-help-center.xyz>',
                                 "Your page will be disabled",
                                 "Your page will be disabled. Appeal within 24 hours: http://bad.link")),
    ("Possible Scam", make_email("Winner Desk <prize@lotto.biz>", "Claim your prize",
                                 "You have won! Pay a small processing fee by gift card.")),
    ("Social Media Notifications", make_email("Facebook <notification@facebookmail.com>",
                                              "Your video has 52M views", "People are reacting to your video.")),
    ("Video Licensing & Rights", make_email("Rights Team <rights@viralhog.com>", "Your video",
                                            "Hi Anthony, we'd love to work with you.")),
    ("Video Licensing & Rights", make_email("Jane <jane@somecompany.com>", "Licensing request for your video",
                                            "We would like to license your video for our compilation. Non-exclusive terms.")),
    ("Media & Press", make_email("Tom Reporter <tom@citynews.com>", "Interview request",
                                 "I'm a reporter writing a story about you and your son. Can we set up an interview?")),
    ("Business & Brand Deals", make_email("Sara <sara@snackbrand.com>", "Paid partnership opportunity",
                                          "We'd love to partner with you on a sponsored post. What are your rates? Budget is flexible.")),
    ("Management & Agencies", make_email("Mike <mike@startalent.com>", "Talent management",
                                         "Our talent agency would love to represent you and grow your page.")),
    ("Fan Mail", make_email("Linda <linda1960@gmail.com>", "Your video made me cry",
                            "I saw your video with your son and it touched my heart. God bless you both.")),
    ("Newsletters & Promotions", make_email("Shoe Store <deals@shoes.com>", "40% off this weekend",
                                            "Shop now, sale ends Sunday.", "List-Unsubscribe: <mailto:u@shoes.com>\n")),
    ("Sent", make_email("Anthony <anthony@example.com>", "Re: hi", "Thanks!", "X-Gmail-Labels: Sent,Inbox\n")),
    ("Needs Review", make_email("Bob <bob@example.org>", "hey", "call me when you get a sec")),
]


class ClassifyTest(unittest.TestCase):
    def test_samples(self):
        for expected, raw in SAMPLES:
            m = S.parse(raw.encode())
            cat, _conf, reason = S.classify(m)
            self.assertEqual(cat, expected, f"{m['subject']!r} -> {cat} ({reason})")

    def test_contacts_are_personal(self):
        m = S.parse(SAMPLES[-1][1].encode())
        self.assertEqual(S.classify(m, frozenset({"bob@example.org"}))[0], "Personal")

    def test_html_only_body(self):
        raw = ("From: a@b.com\nSubject: hi\nContent-Type: text/html\n\n"
               "<p>I <b>love your video</b></p><style>x{}</style>").encode()
        self.assertIn("love your video", S.parse(raw)["body"])
        self.assertNotIn("x{}", S.parse(raw)["body"])

    def test_keyword_needs_word_start(self):
        # "mcn" must not match inside other words
        self.assertEqual(S.score("", "welcome back mcnally")["Management & Agencies"], 0)


class EndToEndTest(unittest.TestCase):
    def test_run_on_mbox(self):
        with tempfile.TemporaryDirectory() as d:
            mbox = os.path.join(d, "mail.mbox")
            with open(mbox, "w") as f:
                f.write("".join(raw for _, raw in SAMPLES))
            out = os.path.join(d, "out")
            S.main([mbox, "--out", out])

            with open(os.path.join(out, "all_emails.csv"), newline="") as f:
                rows = list(csv.DictReader(f))
            self.assertEqual([r["category"] for r in rows], [c for c, _ in SAMPLES])

            with open(os.path.join(out, "priority.csv"), newline="") as f:
                self.assertEqual(len(list(csv.DictReader(f))), 5)
            self.assertTrue(os.path.exists(os.path.join(out, "by_category", "Fan_Mail.mbox")))

            # Each split mbox holds the right number of messages
            scam = list(S.iter_mbox(os.path.join(out, "by_category", "Possible_Scam.mbox")))
            self.assertEqual(len(scam), 2)

            # Claude results override the rules on the next run
            with open(os.path.join(out, "ai_results.csv"), "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["id", "category", "priority", "reason"])
                w.writeheader()
                w.writerow({"id": len(SAMPLES), "category": "Personal", "priority": "normal", "reason": "a friend"})
            self.assertEqual(ai_sort.select_ids(out, "review"), {len(SAMPLES)})
            S.main([mbox, "--out", out])
            with open(os.path.join(out, "all_emails.csv"), newline="") as f:
                last = list(csv.DictReader(f))[-1]
            self.assertEqual((last["category"], last["confidence"]), ("Personal", "ai"))

    def test_ai_request_shape(self):
        m = S.parse(SAMPLES[0][1].encode())
        req = ai_sort.make_request(1, m, "claude-opus-5")
        self.assertEqual(req["custom_id"], "msg-1")
        self.assertIn("Your page will be disabled", req["params"]["messages"][0]["content"])
        self.assertIn("Possible Scam", req["params"]["output_config"]["format"]["schema"]["properties"]["category"]["enum"])


if __name__ == "__main__":
    unittest.main()
