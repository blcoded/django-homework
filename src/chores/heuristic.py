import re

LARGE_PATTERNS = [
    r"\bdeep\s*clean",
    r"\bfridge\b",
    r"\brefrigerator\b",
    r"\boven\b",
    r"\bgarage\b",
    r"\bcarpet\b",
    r"\bwindow(s)?\b",
    r"\bbaseboard(s)?\b",
    r"\bdefrost\b",
    r"\bpaint\b",
    r"\bmove\s+heavy\b",
    r"\bgutter(s)?\b",
    r"\byard\s*work\b",
    r"\bgarden\s*cleanup\b",
]

SMALL_PATTERNS = [
    r"\btrash\b",
    r"\brecycle\b",
    r"\brecycling\b",
    r"\bwipe\b",
    r"\bwater\s+plant(s)?\b",
    r"\bmail\b",
    r"\bdishes\b",
    r"\bdishwasher\b",
    r"\bcounter(s)?\b",
    r"\bdust\b",
    r"\brinse\b",
    r"\brefill\b",
    r"\bfeed\b",
    r"\btowel(s)?\b",
    r"\btidy\b",
]


def suggest_effort_level(title: str, description: str = "") -> str:
    """
    Lightweight heuristic helper that analyzes chore title and description
    to suggest Small, Medium, or Large effort level.
    """
    text = f"{title} {description}".lower().strip()
    if not text:
        return "medium"

    for pattern in LARGE_PATTERNS:
        if re.search(pattern, text):
            return "large"

    for pattern in SMALL_PATTERNS:
        if re.search(pattern, text):
            return "small"

    return "medium"
