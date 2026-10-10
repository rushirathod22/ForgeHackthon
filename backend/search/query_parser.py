from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ParsedQuery:
    raw_query: str
    target_classes: list[str] = field(default_factory=list)
    event_types: list[str] = field(default_factory=list)
    visual_attributes: list[str] = field(default_factory=list)
    min_speed: float | None = None
    min_duration: float | None = None
    # Relative video timestamp filters (seconds from video start)
    time_start_sec: float | None = None
    time_end_sec: float | None = None
    # Absolute wall-clock time filters (seconds since midnight, e.g. 9 PM = 75600.0)
    abs_time_start_sec: float | None = None
    abs_time_end_sec: float | None = None
    zone_name: str | None = None
    keywords: list[str] = field(default_factory=list)
    clothing_colors: list[str] = field(default_factory=list)  # e.g. ["black_shirt", "blue_pants"]
    # Group / count filter: "two persons" → min_group_size=2
    min_group_size: int | None = None
    # Movement direction tags: "going toward stair" → ["going_right", "toward_stair"]
    movement_tags: list[str] = field(default_factory=list)


CLASS_SYNONYMS = {
    "car": ["car", "cars", "automobile", "sedan", "vehicle", "vehicles"],
    "truck": ["truck", "trucks", "lorry", "pickup"],
    "bus": ["bus", "buses"],
    "motorcycle": ["motorcycle", "motorcycles", "bike", "motorbike"],
    "bicycle": ["bicycle", "bicycles", "cycle"],
    "person": [
        "person", "people", "pedestrian", "man", "woman", "human",
        "girl", "boy", "lady", "child", "kid", "female", "male",
        "guard", "watchman", "visitor", "intruder", "stranger",
        "suspect", "suspicious person",
    ],
    # These names match the COCO labels emitted by the YOLO model.  Keep
    # carried-object phrases out of this filter; they are person attributes.
    "cell phone": ["cell phone", "mobile phone", "mobile", "smartphone", "phone"],
    "handbag": ["handbag", "hand bag", "purse", "shopping bag"],
    "backpack": ["backpack", "rucksack", "knapsack"],
}

EVENT_SYNONYMS = {
    "LOITERING": ["loitering", "loiter", "standing", "hanging around", "waiting"],
    "FAST_MOVEMENT": ["fast", "overspeeding", "speeding", "speed", "rapid", "moving fast", "quick", "running"],
    "ZONE_INTRUSION": [
        "intrusion", "intruder", "restricted", "trespass", "trespassing",
        "unauthorized entry", "security breach", "fence jump", "suspicious",
    ],
    "STOPPED_VEHICLE": ["stopped", "stationary", "parked", "halted", "idle"],
    "OBJECT_TRACKED": ["track", "tracked", "seen", "detected", "appeared", "came", "went"],
    "GUARD_ABSENT": [
        "guard absent", "watchman absent", "guard missing", "no guard",
        "guard left", "guard not present", "nobody at gate",
    ],
    "SUSPICIOUS_ENTRY_UNGUARDED": [
        "suspicious entry", "unguarded entry", "entered while guard",
        "entered when guard", "suspicious person entered",
    ],
    "SHOPLIFTING": [
        "shoplifting", "shoplift", "theft", "stealing", "steal", "thief",
        "pocketing", "concealing", "concealment", "putting in bag", "hiding item",
    ],
}

VISUAL_ATTRIBUTES = [
    "white", "black", "silver", "gray", "grey", "red", "blue",
    "yellow", "green", "orange", "purple", "pink",
    "helmet", "backpack", "bag", "hat", "cap", "bow", "ribbon", "headband", "hair", "roof rack",
]

# Clothing part keywords → clothing color tags
CLOTHING_PARTS = {
    "shirt": "shirt",
    "t-shirt": "shirt",
    "tshirt": "shirt",
    "top": "shirt",
    "jacket": "jacket",
    "coat": "jacket",
    "hoodie": "jacket",
    "pants": "pants",
    "jeans": "pants",
    "trousers": "pants",
    "shorts": "pants",
    "dress": "dress",
    "skirt": "dress",
}

ZONE_SYNONYMS = {
    "Exit": ["exit gate", "exit door", "exit", "way out", "checkout", "front exit", "back exit"],
    "MainGate": ["main gate", "society gate", "gate 1", "gate no 1", "gate one", "entrance", "entry", "gate"],
    "Gate2": ["gate 2", "gate no 2", "second gate", "gate two"],
    "Parking": ["parking", "parking area", "parking lot"],
    "Warehouse": ["warehouse", "loading bay", "yard"],
}

# Carried-item / accessory phrases → visual attribute tag
# These map to the tags injected by the co-location tagger in detect.py
CARRIED_ITEM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:holding|using|with|checking|scrolling|looking\s+at)\s+(?:a\s+|an\s+|the\s+|their\s+)?(?:cell\s*)?(?:phone|mobile|smartphone)\b", re.I), "holding_phone"),
    (re.compile(r"\b(?:on\s+(?:the|their|a)?\s*(?:cell\s*)?phone|texting)\b", re.I), "holding_phone"),
    (re.compile(r"\b(?:holding|carrying|with)\s+(?:a\s+|an\s+|the\s+)?(?:handbag|bag|purse|clutch)\b", re.I), "holding_bag"),
    (re.compile(r"\b(?:wearing|carrying|with)\s+(?:a\s+|an\s+|the\s+)?(?:backpack|rucksack|knapsack|bagpack)\b", re.I), "wearing_backpack"),
    (re.compile(r"\b(?:wearing|with)\s+(?:a\s+|an\s+|the\s+)?helmet\b", re.I), "wearing_helmet"),
]

CARRIED_ITEMS: dict[str, str] = {
    # phone
    "with phone":        "holding_phone",
    "holding phone":     "holding_phone",
    "using phone":       "holding_phone",
    "on phone":          "holding_phone",
    "talking on phone":  "holding_phone",
    "with mobile":       "holding_phone",
    "using mobile":      "holding_phone",
    "with cell phone":   "holding_phone",
    "holding cell phone":"holding_phone",
    "on the phone":      "holding_phone",
    "texting":           "holding_phone",
    "scrolling phone":   "holding_phone",
    "on their phone":    "holding_phone",
    "looking at phone":  "holding_phone",
    "checking phone":    "holding_phone",
    # bag / handbag
    "with bag":          "holding_bag",
    "carrying bag":      "holding_bag",
    "holding bag":       "holding_bag",
    "with handbag":      "holding_bag",
    "carrying handbag":  "holding_bag",
    "with purse":        "holding_bag",
    # backpack
    "with backpack":      "wearing_backpack",
    "wearing backpack":   "wearing_backpack",
    "carrying backpack":  "wearing_backpack",
    "with rucksack":      "wearing_backpack",
}

# Tags from CARRIED_ITEMS that the retriever should treat as hard filters
# (candidate must possess the tag or be excluded entirely).
# Kept here so both query_parser and retriever import from the same source.
HARD_FILTER_ATTRS: frozenset[str] = frozenset({
    "holding_phone",
    "holding_bag",
    "wearing_backpack",
})

# ── Count / group synonyms ────────────────────────────────────────────────────
# "two persons", "a pair", "group of three" → min_group_size
COUNT_SYNONYMS: dict[int, list[str]] = {
    2: ["two persons", "two people", "two men", "two women", "2 persons", "2 people", "pair of", "couple of", "both persons", "duo"],
    3: ["three persons", "three people", "3 persons", "3 people", "trio of", "trio"],
    4: ["four persons", "four people", "4 persons", "4 people"],
    5: ["five persons", "five people", "5 persons", "5 people"],
}
# Generic group (unknown count ≥2)
GROUP_PHRASES = [
    "group", "groups", "several", "multiple", "many people",
    "a bunch", "crowd", "crowd of", "together", "moving together",
    "walking together", "going together",
]

# ── Movement direction phrases → direction tag ───────────────────────────────
# Tags must match what detect.py computes and stores in visual_attributes
DIRECTION_PHRASES: dict[str, list[str]] = {
    # General direction from trajectory
    "going_right": [
        "going right", "moving right", "walking right", "heading right",
        "toward the right", "to the right",
    ],
    "going_left": [
        "going left", "moving left", "walking left", "heading left",
        "toward the left", "to the left",
    ],
    "going_up": [
        "going up", "moving up", "walking up", "heading up",
        "upward", "upstairs", "climbing",
    ],
    "going_down": [
        "going down", "moving down", "walking down", "heading down",
        "downward", "downstairs", "descending",
    ],
    # Scene-specific named destinations (map to closest direction tag)
    "toward_stair": [
        "toward stair", "toward stairs", "toward the stair", "toward the stairs",
        "to the stair", "to stairs", "going to stair", "going to stairs",
        "walking to stair", "walking to stairs", "heading to stair",
        "up the stair", "toward staircase", "to staircase", "near stair",
    ],
    "toward_door": [
        "toward door", "toward the door", "to the door", "entering door",
        "walking to door", "heading to door",
    ],
    "toward_exit": [
        "toward exit gate", "towards exit gate", "to exit gate", "to the exit gate",
        "go to exit gate", "going to exit gate", "heading to exit gate", "walking to exit gate",
        "toward exit", "towards exit", "toward the exit", "towards the exit",
        "to exit", "to the exit", "go to exit", "going to exit", "walk to exit",
        "walking to exit", "heading to exit", "head to exit",
        "leaving", "exiting", "going out", "walk out", "walking out",
    ],
    "toward_entrance": [
        "toward entrance", "toward the entrance", "towards entrance", "towards the entrance",
        "entering", "coming in", "toward main gate", "approaching gate", "heading to entrance",
    ],
    # Group movement
    "moving_with_others": [
        "together", "moving together", "walking together", "going together",
        "side by side", "as a group",
    ],
}

TIME_OF_DAY = {
    "night": (21, 6),       # 9 PM – 6 AM (wraps midnight)
    "midnight": (23, 1),
    "morning": (6, 12),
    "afternoon": (12, 17),
    "evening": (17, 21),
    "dawn": (5, 7),
    "dusk": (17, 20),
}


def _parse_12h_to_secs(hour: int, minute: int, period: str) -> float:
    """Convert 12-hour clock time to seconds since midnight."""
    period = period.lower()
    if period == "am":
        if hour == 12:
            hour = 0
    else:  # pm
        if hour != 12:
            hour += 12
    return float(hour * 3600 + minute * 60)


def _parse_24h_to_secs(hour: int, minute: int) -> float:
    return float(hour * 3600 + minute * 60)


def _extract_absolute_time(text: str) -> float | None:
    """
    Try to parse an absolute wall-clock time from text.
    Supports: '9 PM', '9:30 PM', '21:00', '21:30', '9pm', '10:42 AM'
    Returns seconds since midnight, or None if no match.
    """
    # Pattern: HH:MM AM/PM
    m = re.search(r"(\d{1,2}):(\d{2})\s*(am|pm)", text, re.IGNORECASE)
    if m:
        return _parse_12h_to_secs(int(m.group(1)), int(m.group(2)), m.group(3))

    # Pattern: H AM/PM (no minutes)
    m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text, re.IGNORECASE)
    if m:
        return _parse_12h_to_secs(int(m.group(1)), 0, m.group(2))

    # Pattern: HH:MM (24h)
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return _parse_24h_to_secs(h, mn)

    return None


TYPO_FIXES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\boman\b", re.I), "woman"),
    (re.compile(r"\bwman\b", re.I), "woman"),
    (re.compile(r"\bwomn\b", re.I), "woman"),
    (re.compile(r"\bwomam\b", re.I), "woman"),
    (re.compile(r"\bwimen\b", re.I), "women"),
    (re.compile(r"\btoard\b", re.I), "toward"),
    (re.compile(r"\btoards\b", re.I), "toward"),
    (re.compile(r"\btoword\b", re.I), "toward"),
    (re.compile(r"\btowords\b", re.I), "toward"),
    (re.compile(r"\btowrd\b", re.I), "toward"),
    (re.compile(r"\btowrds\b", re.I), "toward"),
    (re.compile(r"\btward\b", re.I), "toward"),
    (re.compile(r"\btwards\b", re.I), "toward"),
    (re.compile(r"\bexite\b", re.I), "exit"),
    (re.compile(r"\bexitt\b", re.I), "exit"),
    (re.compile(r"\bexist\s+gate\b", re.I), "exit gate"),
    (re.compile(r"\bgat\b", re.I), "gate"),
    (re.compile(r"\bpersn\b", re.I), "person"),
    (re.compile(r"\bperosn\b", re.I), "person"),
    (re.compile(r"\bpeple\b", re.I), "people"),
    (re.compile(r"\bpeopel\b", re.I), "people"),
    (re.compile(r"\bclothe\b", re.I), "clothes"),
    (re.compile(r"\bjaket\b", re.I), "jacket"),
    (re.compile(r"\bjacet\b", re.I), "jacket"),
    (re.compile(r"\bshrt\b", re.I), "shirt"),
    (re.compile(r"\bpnts\b", re.I), "pants"),
    (re.compile(r"\bcolr\b", re.I), "color"),
    (re.compile(r"\brad\b", re.I), "red"),
    (re.compile(r"\bblu\b", re.I), "blue"),
    (re.compile(r"\bblck\b", re.I), "black"),
    (re.compile(r"\bwht\b", re.I), "white"),
    (re.compile(r"\bshopliftng\b", re.I), "shoplifting"),
    (re.compile(r"\bshoplfting\b", re.I), "shoplifting"),
    (re.compile(r"\bthefet\b", re.I), "theft"),
    (re.compile(r"\bsteeling\b", re.I), "stealing"),
]


class NLQueryParser:
    """Parses natural language CCTV search prompts into structured query filters."""

    def parse(self, query_text: str) -> ParsedQuery:
        text_lower = query_text.lower().strip()
        for typo_pat, replacement in TYPO_FIXES:
            text_lower = typo_pat.sub(replacement, text_lower)
        parsed = ParsedQuery(raw_query=query_text)

        # ── 1. Class Extraction ─────────────────────────────────────────────
        # A phrase such as "person holding a phone" describes the person
        # track.  The phone is resolved below as a co-located attribute rather
        # than making one database row match two incompatible class names.
        carried_object_terms = {
            "cell phone": "holding_phone",
            "mobile phone": "holding_phone",
            "mobile": "holding_phone",
            "smartphone": "holding_phone",
            "phone": "holding_phone",
            "handbag": "holding_bag",
            "hand bag": "holding_bag",
            "purse": "holding_bag",
            "shopping bag": "holding_bag",
            "backpack": "wearing_backpack",
            "rucksack": "wearing_backpack",
            "knapsack": "wearing_backpack",
        }
        carried_object_requested = any(
            term in text_lower
            and re.search(
                rf"\b(?:holding|carrying|wearing|with|using|checking|scrolling|"
                rf"looking\s+at|on)\b.{{0,20}}\b{re.escape(term)}\b",
                text_lower,
            )
            for term in carried_object_terms
        )
        for norm_class, synonyms in CLASS_SYNONYMS.items():
            for syn in synonyms:
                if (
                    re.search(rf"\b{re.escape(syn)}\b", text_lower)
                    and not (
                        norm_class in {"cell phone", "handbag", "backpack"}
                        and carried_object_requested
                    )
                ):
                    if norm_class not in parsed.target_classes:
                        parsed.target_classes.append(norm_class)

        # ── 2. Event Type Extraction ────────────────────────────────────────
        for norm_event, synonyms in EVENT_SYNONYMS.items():
            for syn in synonyms:
                if syn in text_lower:
                    if norm_event not in parsed.event_types:
                        parsed.event_types.append(norm_event)

        # ── 3. Visual Attributes (plain colors, accessories) ────────────────
        for attr in VISUAL_ATTRIBUTES:
            if re.search(rf"\b{re.escape(attr)}\b", text_lower):
                if attr not in parsed.visual_attributes:
                    parsed.visual_attributes.append(attr)

        # ── 3b. Clothing-part color tags ("black shirt", "blue pants") ───────
        colors_in_query: list[str] = [
            a for a in VISUAL_ATTRIBUTES
            if a in ("white", "black", "silver", "gray", "grey", "red",
                     "blue", "yellow", "green", "orange", "purple", "pink")
            and re.search(rf"\b{re.escape(a)}\b", text_lower)
        ]
        for color in colors_in_query:
            for part_kw, part_tag in CLOTHING_PARTS.items():
                pattern = rf"\b{re.escape(color)}\b.{{0,15}}\b{re.escape(part_kw)}\b"
                if re.search(pattern, text_lower):
                    tag = f"{color}_{part_tag}"  # e.g. "black_shirt"
                    if tag not in parsed.clothing_colors:
                        parsed.clothing_colors.append(tag)
                    # Upper-body clothing (jacket, shirt, top) should match each other
                    if part_tag in ("shirt", "jacket"):
                        alt_tag = f"{color}_shirt" if part_tag == "jacket" else f"{color}_jacket"
                        if alt_tag not in parsed.clothing_colors:
                            parsed.clothing_colors.append(alt_tag)
                    # Also ensure base color is in visual_attributes
                    if color not in parsed.visual_attributes:
                        parsed.visual_attributes.append(color)
                    # Clothing on a person
                    if "person" not in parsed.target_classes:
                        parsed.target_classes.append("person")

        # ── 3c. Carried-item / accessory detection ("person with phone", "carrying bag") ───
        for pattern, attr_tag in CARRIED_ITEM_PATTERNS:
            if pattern.search(text_lower):
                if attr_tag not in parsed.visual_attributes:
                    parsed.visual_attributes.append(attr_tag)
                if "person" not in parsed.target_classes:
                    parsed.target_classes.append("person")

        for phrase, attr_tag in CARRIED_ITEMS.items():
            if phrase in text_lower:
                if attr_tag not in parsed.visual_attributes:
                    parsed.visual_attributes.append(attr_tag)
                # Carried items imply a person
                if "person" not in parsed.target_classes:
                    parsed.target_classes.append("person")

        # ── 3d. Zone / location extraction ─────────────────────────────────────────────────────────────────────
        for norm_zone, synonyms in ZONE_SYNONYMS.items():
            for syn in synonyms:
                if syn in text_lower:
                    parsed.zone_name = norm_zone
                    break
            if parsed.zone_name:
                break

        # ── 3e. Count / group size ("two persons", "a group") ────────────────
        for count, phrases in COUNT_SYNONYMS.items():
            for phrase in phrases:
                if re.search(r"\b" + re.escape(phrase) + r"\b", text_lower):
                    parsed.min_group_size = count
                    if "person" not in parsed.target_classes:
                        parsed.target_classes.append("person")
                    break
            if parsed.min_group_size:
                break

        # Generic group phrases (size ≥2, unknown exact count)
        if parsed.min_group_size is None:
            for phrase in GROUP_PHRASES:
                if re.search(r"\b" + re.escape(phrase) + r"\b", text_lower):
                    parsed.min_group_size = 2
                    if "person" not in parsed.target_classes:
                        parsed.target_classes.append("person")
                    break

        # ── 3f. Movement direction ("going toward stair", "walking right") ───
        for direction_tag, phrases in DIRECTION_PHRASES.items():
            for phrase in phrases:
                if phrase in text_lower:
                    if direction_tag not in parsed.movement_tags:
                        parsed.movement_tags.append(direction_tag)
                    break

        # ── 4. Speed Modifiers ───────────────────────────────────────────────
        if "fast" in text_lower or "speeding" in text_lower or "overspeeding" in text_lower:
            parsed.min_speed = 50.0


        # ── 5a. Relative time (seconds from video start) ─────────────────────
        after_match = re.search(r"after\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?(?!\s*(?:am|pm))", text_lower)
        if after_match:
            parsed.time_start_sec = float(after_match.group(1))

        before_match = re.search(r"before\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?(?!\s*(?:am|pm))", text_lower)
        if before_match:
            parsed.time_end_sec = float(before_match.group(1))

        between_match = re.search(
            r"between\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?\s+(?:and|to|-)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?(?!\s*(?:am|pm))",
            text_lower,
        )
        if between_match:
            parsed.time_start_sec = float(between_match.group(1))
            parsed.time_end_sec = float(between_match.group(2))

        first_match = re.search(r"first\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)", text_lower)
        if first_match:
            parsed.time_start_sec = 0.0
            parsed.time_end_sec = float(first_match.group(1))

        duration_match = re.search(r"(?:for|longer than|more than)\s+(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)", text_lower)
        if duration_match:
            parsed.min_duration = float(duration_match.group(1))

        # ── 5b. Absolute wall-clock time (9 PM, 21:00, "after 9 PM") ─────────
        # "after X PM/AM" or "after HH:MM"
        after_abs = re.search(r"after\s+(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)", text_lower)
        if after_abs:
            t = _extract_absolute_time(after_abs.group(1))
            if t is not None:
                parsed.abs_time_start_sec = t

        # "before X PM/AM"
        before_abs = re.search(r"before\s+(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)", text_lower)
        if before_abs:
            t = _extract_absolute_time(before_abs.group(1))
            if t is not None:
                parsed.abs_time_end_sec = t

        # "between X PM and Y PM"
        between_abs = re.search(
            r"between\s+(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)\s+(?:and|to|-)\s+(\d{1,2}(?::\d{2})?(?:\s*(?:am|pm))?)",
            text_lower,
        )
        if between_abs:
            t1 = _extract_absolute_time(between_abs.group(1))
            t2 = _extract_absolute_time(between_abs.group(2))
            if t1 is not None:
                parsed.abs_time_start_sec = t1
            if t2 is not None:
                parsed.abs_time_end_sec = t2

        # "at night", "in the morning", etc.
        for tod_name, (h_start, h_end) in TIME_OF_DAY.items():
            if tod_name in text_lower:
                parsed.abs_time_start_sec = float(h_start * 3600)
                if h_end > h_start:
                    parsed.abs_time_end_sec = float(h_end * 3600)
                else:
                    # Wraps midnight (e.g. night: 21:00 → 06:00 next day)
                    parsed.abs_time_end_sec = float(h_end * 3600 + 86400)
                break

        # ── 6. Extract residual keywords ────────────────────────────────────
        words = re.findall(r"\b\w+\b", text_lower)
        stop_words = {
            "show", "find", "search", "all", "the", "in", "near", "at", "me", "for",
            "with", "a", "an", "to", "and", "or", "from", "video", "cctv", "camera",
            "who", "what", "when", "where", "how", "did", "does", "has", "have",
            "is", "was", "were", "are", "that", "this", "there", "which",
        }
        parsed.keywords = [w for w in words if w not in stop_words]

        return parsed
