"""Grievance classification: category, priority and routing department.

This is a transparent rule-based classifier over bilingual keyword sets, not a
trained model — describe it that way in the report. It runs server-side so the
same rules apply whether a complaint arrives from the citizen portal, an
officer's desk, or the API directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "Water": [
        "water", "pipeline", "tap", "well", "borewell", "tank", "leak", "supply",
        "पाणी", "नळ", "गळती", "विहीर", "टाकी", "पाईप",
    ],
    "Sanitation": [
        "drain", "drainage", "garbage", "waste", "toilet", "sewage", "clog", "dirty",
        "गटार", "कचरा", "स्वच्छता", "शौचालय", "सांडपाणी", "तुंबले",
    ],
    "Roads": [
        "road", "pothole", "street", "footpath", "bridge", "lane", "transport",
        "रस्ता", "खड्डा", "पूल", "गल्ली", "वाहतूक",
    ],
    "Electricity": [
        "electricity", "power", "streetlight", "street light", "light", "transformer",
        "outage", "pole",
        "वीज", "दिवा", "पथदिवा", "ट्रान्सफॉर्मर", "खांब",
    ],
    "Health": [
        "health", "hospital", "clinic", "doctor", "medicine", "anganwadi", "disease",
        "आरोग्य", "दवाखाना", "डॉक्टर", "औषध", "अंगणवाडी", "आजार",
    ],
}

DEPARTMENTS: dict[str, tuple[str, str]] = {
    "Water": ("Water Works Department", "पाणी पुरवठा विभाग"),
    "Sanitation": ("Sanitation Cell", "स्वच्छता कक्ष"),
    "Roads": ("Public Works Department", "सार्वजनिक बांधकाम विभाग"),
    "Electricity": ("Electricity Board Liaison", "वीज मंडळ समन्वय कक्ष"),
    "Health": ("Primary Health Cell", "प्राथमिक आरोग्य कक्ष"),
    "Other": ("General Administration", "सामान्य प्रशासन"),
}

CATEGORY_MR: dict[str, str] = {
    "Water": "पाणी", "Sanitation": "स्वच्छता", "Roads": "रस्ते",
    "Electricity": "वीज", "Health": "आरोग्य", "Other": "इतर",
}

PRIORITY_MR: dict[str, str] = {
    "Critical": "अत्यावश्यक", "High": "उच्च", "Medium": "मध्यम", "Low": "कमी",
}

# Words that escalate regardless of category.
CRITICAL_TERMS = [
    "contaminat", "sewage mix", "collapse", "electrocut", "shock", "outbreak",
    "epidemic", "no water for", "child", "accident", "injur", "fire",
    "दूषित", "कोसळ", "विजेचा धक्का", "साथ", "अपघात", "जखमी", "आग",
]
HIGH_TERMS = [
    "urgent", "immediately", "days", "week", "overflow", "burst", "blocked",
    "danger", "unsafe", "school", "hospital",
    "तातडी", "त्वरित", "फुटली", "तुंबले", "धोका", "असुरक्षित", "शाळा",
]
LOW_TERMS = ["request", "suggest", "would like", "minor", "विनंती", "सूचना", "किरकोळ"]


# ─────────────────────────────────────────────────────────────────────────────
# Repair, or a request for new work
#
# "The streetlight is broken" and "we need twenty more streetlights" land in the
# same category and are different kinds of thing. The first is closed by a
# repair. The second cannot be closed by anyone at a desk: it needs the need
# checked, a decision by the Panchayat, an estimate, money, and a work — so it
# has to become a project rather than sit in the complaint queue marked Pending.
#
# Rules, like the rest of this module, and for the same reason: the officer has
# to be able to see why the system said what it said. The officer confirms or
# changes the answer before anything is built on it.
# ─────────────────────────────────────────────────────────────────────────────

REQUEST_TYPE_MR: dict[str, str] = {"service": "दुरुस्ती / सेवा", "development": "नवीन काम"}

# Something that exists has stopped working. Any of these wins outright: "we need
# the hand pump fixed" is a repair however it is phrased.
REPAIR_TERMS = [
    "broken", "not working", "repair", "fix", "leak", "damaged", "clog", "blocked",
    "burst", "fault", "overflow", "collapsed", "stopped", "no water", "pothole",
    "not collected", "outage",
    "बंद", "दुरुस्त", "गळती", "तुटल", "फुटल", "तुंबल", "खराब", "नादुरुस्त", "खड्ड",
]
# Asking for something that is not there yet.
NEW_WORK_TERMS = [
    "new ", "additional", "install", "construct", "build", "extension", "extend",
    "sanction",
    "नवीन", "अतिरिक्त", "बसव", "बांध", "आणखी", "वाढव", "मंजूर",
]
# Too common to mean anything alone ("we need water"), but with a number beside
# them they are a request for a quantity of something ("need 5 more taps").
WEAK_NEW_WORK_TERMS = ["need", "require", "provide", "more ", "हवे", "हवी", "हवा", "गरज"]

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
# A number straight after one of these names a place, not a quantity.
_PLACE_WORDS = ("ward", "ward no", "ward no.", "lane", "road", "plot", "survey",
                "प्रभाग", "वॉर्ड", "वार्ड", "गल्ली")
# A number straight before one of these is a duration.
_TIME_WORDS = ("day", "week", "month", "year", "hour", "दिवस", "आठवड", "महिन", "वर्ष", "तास")


def extract_quantity(text: str) -> int | None:
    """The first number in the text that reads as a count of things.

    "Ward 3 needs 20 streetlights, dark for 2 months" has three numbers and one
    quantity. The ward number and the duration are skipped by what stands next
    to them; whatever is left first is the answer. Wrong sometimes, which is why
    the officer sees it as a suggestion in an editable field.
    """
    text = text.translate(_DEVANAGARI_DIGITS).lower()
    for match in re.finditer(r"(?<![\w.])(\d{1,4})(?![\d.])", text):
        before = text[max(0, match.start() - 14):match.start()].rstrip(" .:-#")
        after = text[match.end():match.end() + 12].lstrip(" -")
        if before.endswith(_PLACE_WORDS):
            continue
        if after.startswith(_TIME_WORDS) or after.startswith("%"):
            continue
        value = int(match.group(1))
        if value >= 1:
            return value
    return None


def detect_request_type(text: str) -> tuple[str, int | None]:
    """('service' | 'development', quantity or None)."""
    lowered = text.lower()
    if any(term in lowered for term in REPAIR_TERMS):
        return "service", None

    quantity = extract_quantity(text)
    if any(term in lowered for term in NEW_WORK_TERMS):
        return "development", quantity
    if quantity is not None and any(term in lowered for term in WEAK_NEW_WORK_TERMS):
        return "development", quantity
    return "service", None


def keyword_hits(text: str) -> dict[str, list[str]]:
    """The keywords of each category that `text` contains.

    Matching is by substring, on purpose: "streetlights", "leaking" and
    "potholes" should match their stems without a list of every inflection. The
    cost is that a short keyword turns up inside a longer one that means
    something else. "Streetlight" contains "street", so a complaint about a dark
    lane scored two points for Roads before it scored anything for Electricity,
    and was routed to Public Works. Marathi has the same trap: सांडपाणी, sewage,
    contains पाणी, water.

    So a keyword found only inside a longer keyword of a *different* category is
    not counted — the longer word is what the person wrote. Within one category
    nothing changes: "drainage" still counts for both itself and "drain".
    """
    found: list[tuple[int, int, str, str]] = []
    for category, words in CATEGORY_KEYWORDS.items():
        for word in words:
            needle = word.lower()
            start = text.find(needle)
            while start != -1:
                found.append((start, start + len(needle), category, word))
                start = text.find(needle, start + 1)

    hits: dict[str, list[str]] = {}
    for start, end, category, word in found:
        swallowed = any(
            other != category
            and o_start <= start
            and end <= o_end
            and (o_end - o_start) > (end - start)
            for o_start, o_end, other, _ in found
        )
        if not swallowed and word not in hits.setdefault(category, []):
            hits[category].append(word)
    return {category: words for category, words in hits.items() if words}


@dataclass
class Classification:
    category: str
    category_mr: str
    priority: str
    priority_mr: str
    department: str
    department_mr: str
    matched_terms: list[str]
    request_type: str = "service"
    request_type_mr: str = REQUEST_TYPE_MR["service"]
    requested_quantity: int | None = None


def classify(title: str, description: str = "") -> Classification:
    text = f"{title} {description}".lower()

    # Category: whichever keyword set has the most hits, and no hits means
    # Other. A tie goes to the category whose longest matched word is longer —
    # "streetlight" says more about a complaint than "road" does — and only
    # then to whichever is listed first.
    hits = keyword_hits(text)
    scores = {
        category: (len(words), max(len(word) for word in words))
        for category, words in hits.items()
    }
    matched = [word for words in hits.values() for word in words]

    category = max(scores, key=lambda k: scores[k]) if scores else "Other"

    # Priority: escalation terms first, then category-specific defaults.
    if any(t in text for t in CRITICAL_TERMS):
        priority = "Critical"
    elif any(t in text for t in HIGH_TERMS):
        priority = "High"
    elif any(t in text for t in LOW_TERMS):
        priority = "Low"
    elif category in ("Water", "Health"):
        # Drinking water and health complaints default up, not down.
        priority = "High"
    elif category == "Other":
        priority = "Low"
    else:
        priority = "Medium"

    request_type, quantity = detect_request_type(f"{title} {description}")

    dept, dept_mr = DEPARTMENTS[category]
    return Classification(
        category=category,
        category_mr=CATEGORY_MR[category],
        priority=priority,
        priority_mr=PRIORITY_MR[priority],
        department=dept,
        department_mr=dept_mr,
        matched_terms=sorted(set(matched)),
        request_type=request_type,
        request_type_mr=REQUEST_TYPE_MR[request_type],
        requested_quantity=quantity,
    )
