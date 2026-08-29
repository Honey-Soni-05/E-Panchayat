"""Grievance classification: category, priority and routing department.

This is a transparent rule-based classifier over bilingual keyword sets, not a
trained model — describe it that way in the report. It runs server-side so the
same rules apply whether a complaint arrives from the citizen portal, an
officer's desk, or the API directly.
"""

from __future__ import annotations

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
        "electricity", "power", "streetlight", "light", "transformer", "outage", "pole",
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


@dataclass
class Classification:
    category: str
    category_mr: str
    priority: str
    priority_mr: str
    department: str
    department_mr: str
    matched_terms: list[str]


def classify(title: str, description: str = "") -> Classification:
    text = f"{title} {description}".lower()

    # Category: whichever keyword set has the most hits; ties go to the first
    # listed, and no hits means Other.
    scores: dict[str, int] = {}
    matched: list[str] = []
    for category, words in CATEGORY_KEYWORDS.items():
        hits = [w for w in words if w.lower() in text]
        if hits:
            scores[category] = len(hits)
            matched.extend(hits)

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

    dept, dept_mr = DEPARTMENTS[category]
    return Classification(
        category=category,
        category_mr=CATEGORY_MR[category],
        priority=priority,
        priority_mr=PRIORITY_MR[priority],
        department=dept,
        department_mr=dept_mr,
        matched_terms=sorted(set(matched)),
    )
