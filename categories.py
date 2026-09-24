"""
Category definitions and keyword rules for sorting a viral creator's inbox.

This is the file to edit if you want to tweak how emails get sorted:
add a keyword, add a sender domain, or rename a category. Keywords are
matched case-insensitively against the subject (counts double) and the
first part of the email body.
"""

# Display order for reports. Each category gets its own output mailbox file.
CATEGORIES = [
    "Business & Brand Deals",
    "Video Licensing & Rights",
    "Media & Press",
    "Management & Agencies",
    "Fan Mail",
    "Possible Scam",
    "Social Media Notifications",
    "Newsletters & Promotions",
    "Personal",
    "Sent",
    "Needs Review",
]

# Categories worth reading first -- money, deadlines, or reputation.
PRIORITY_CATEGORIES = {
    "Business & Brand Deals",
    "Video Licensing & Rights",
    "Media & Press",
    "Management & Agencies",
}

# Descriptions are shown in the report and given to Claude in AI mode.
DESCRIPTIONS = {
    "Business & Brand Deals": "Sponsorships, brand partnerships, paid promotions, collabs, product seeding, speaking or appearance offers.",
    "Video Licensing & Rights": "Requests to license, feature, repost, or buy rights to the viral video (Jukin, ViralHog, Storyful, Newsflare, TV shows, compilation channels).",
    "Media & Press": "Journalists, news outlets, TV/radio producers, podcasts asking for interviews, quotes, or comment.",
    "Management & Agencies": "Talent managers, agents, MCNs, and creator agencies offering representation.",
    "Fan Mail": "Messages from viewers reacting to the video, sharing their story, or sending support.",
    "Possible Scam": "Phishing, fake 'Facebook/Meta' security or verification notices, fake copyright strikes, crypto/gift-card/money requests. Do not click links.",
    "Social Media Notifications": "Automated notifications from Facebook, Instagram, TikTok, YouTube, etc.",
    "Newsletters & Promotions": "Marketing emails, newsletters, receipts and other bulk mail.",
    "Personal": "Friends, family and known contacts.",
    "Sent": "Emails Anthony sent himself.",
    "Needs Review": "Could not be confidently sorted -- review manually or run AI mode.",
}

# Real sender domains for platform notifications. A sender that *claims* to
# be Facebook/Meta but isn't from one of these is treated as a possible scam.
PLATFORM_DOMAINS = {
    "facebookmail.com", "facebook.com", "meta.com", "metamail.com",
    "instagram.com", "mail.instagram.com", "tiktok.com", "tiktokv.com",
    "youtube.com", "google.com", "accounts.google.com", "x.com", "twitter.com",
    "snapchat.com", "linkedin.com", "linkedinmail.com", "threads.net",
}
PLATFORM_NAMES = ["facebook", "meta", "instagram", "tiktok", "youtube", "copyright team", "page support"]

# Known viral-video licensing companies -- almost always licensing requests.
LICENSING_DOMAINS = {
    "jukinmedia.com", "jukin.com", "viralhog.com", "storyful.com", "newsflare.com",
    "collab.com", "rumble.com", "viralbe.com", "caters.co.uk", "swns.com",
    "whistle.com", "ladbible.com", "unilad.com", "thedodo.com", "dodo.com",
}

# Keyword rules. Keywords match whole words; end one with "*" to match any
# ending (e.g. "licens*" matches license, licensing, licensed). Weight = how strongly a single hit points at the category.
KEYWORDS = {
    "Possible Scam": {
        3: [
            "verification badge", "blue badge", "blue tick", "get verified",
            "your page will be deleted", "your page will be disabled",
            "account will be disabled", "account will be deleted", "account has been restricted",
            "appeal within 24 hours", "appeal within 48 hours", "confirm your identity",
            "gift card", "western union", "moneygram", "bitcoin", "crypto investment",
            "claim your prize", "you have won", "lottery", "wire transfer fee",
            "send your password", "login details", "seed phrase", "processing fee",
            "unclaimed funds", "inheritance", "next of kin",
        ],
        2: ["violated our community standards", "copyright infringement notice", "urgent action required", "click here to appeal"],
    },
    "Video Licensing & Rights": {
        3: [
            "license your video", "licensing your video", "license the video", "licensing request",
            "licensing agreement", "exclusive rights", "non-exclusive", "usage rights",
            "rights to your video", "rights to the video", "permission to use your video",
            "permission to share your video", "permission to feature", "feature your video",
            "use your video", "use your clip", "repost your video", "footage", "clip license",
        ],
        2: ["licens*", "royalt*", "revenue share", "compilation", "viral video", "rights management"],
    },
    "Media & Press": {
        3: [
            "interview request", "request for comment", "for comment", "press inquiry",
            "media inquiry", "journalist", "reporter", "producer at", "segment",
            "on air", "on-air", "podcast guest", "be a guest", "our show", "news story",
            "writing a story", "writing an article", "live on", "tv appearance",
        ],
        2: ["interview*", "podcast*", "newsroom", "news", "morning show", "radio", "magazine", "press"],
    },
    "Management & Agencies": {
        3: [
            "talent management", "represent you", "representation", "talent agency",
            "management company", "sign with us", "creator management", "mcn",
            "grow your page", "monetize your page", "manage your page",
        ],
        2: ["manager", "agency", "talent", "management"],
    },
    "Business & Brand Deals": {
        3: [
            "brand deal", "sponsorship", "sponsored post", "paid partnership", "paid collaboration",
            "brand partnership", "partner with you", "collaborate with you", "collab*",
            "ambassador", "influencer campaign", "campaign brief", "rate card", "your rates",
            "media kit", "promote our", "gifted", "send you our product", "speaking engagement",
            "appearance fee", "booking", "endorsement",
        ],
        2: ["partnership*", "campaign*", "budget", "compensation", "proposal", "opportunit*", "sponsor*", "brand*"],
    },
    "Fan Mail": {
        3: [
            "love your video", "loved your video", "saw your video", "watched your video",
            "made me cry", "brought tears", "your son", "you and your son", "such a good dad",
            "great dad", "amazing father", "god bless", "so proud of you", "you inspired",
            "inspired me", "beautiful video", "touched my heart", "biggest fan", "big fan",
        ],
        2: ["your video", "adorable", "so sweet", "heartwarming", "blessed", "congrat*"],
    },
    "Newsletters & Promotions": {
        2: ["unsubscribe", "view in browser", "newsletter", "% off", "sale ends", "shop now", "order confirmation", "receipt"],
    },
}

# Minimum score to accept a keyword-based category; below this -> Needs Review.
MIN_SCORE = 3
