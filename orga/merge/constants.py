
# Social Media Platforms and their sharing patterns
SOCIAL_PLATFORMS = {
    "facebook": {
        "domains": ["facebook.com", "fb.com"],
        "blacklisted_paths": [r"/sharer\.php", r"/sharer/sharer\.php", r"/sharer", r"/posts", r"/watch", r"/hashtag"],
        "canonical_domain": "facebook.com"
    },
    "linkedin": {
        "domains": ["linkedin.com"],
        "blacklisted_paths": [r"/shareArticle", r"/sharing/share-offsite", r"/sharing", r"/posts", r"/feed"],
        "canonical_domain": "linkedin.com"
    },
    "twitter": {
        "domains": ["twitter.com", "t.co", "x.com"],
        "blacklisted_paths": [r"/home", r"/intent/tweet", r"/share", r"/intent", r"/hashtag", r"/status"],
        "canonical_domain": "twitter.com"
    },
    "instagram": {
        "domains": ["instagram.com"],
        "blacklisted_paths": [r"/p/", r"/reel", r"/reels", r"/explore"],
        "canonical_domain": "instagram.com"
    },
    "youtube": {
        "domains": ["youtube.com", "youtu.be"],
        "blacklisted_paths": [r"/share", r"/watch", r"/shorts"],
        "canonical_domain": "youtube.com"
    }
}

# Generic sharing patterns found in queries
GENERIC_SHARING_QUERY_KEYS = ["share", "sharing", "u", "url", "status", "text"]

# Address Abbreviations for normalization
ADDRESS_ABBREVIATIONS = {
    r"\brd\.?\b": "Road",
    r"\bst\.?\b": "Street",
    r"\bave\.?\b": "Avenue",
    r"\bblvd\.?\b": "Boulevard",
    r"\bln\.?\b": "Lane",
    r"\bdr\.?\b": "Drive",
    r"\bct\.?\b": "Court",
    r"\bsq\.?\b": "Square",
    r"\bcir\.?\b": "Circle"
}

# Phone filtering constants
PHONE_MIN_DIGITS = 7
PHONE_MAX_REPETITION_RATIO = 0.8
