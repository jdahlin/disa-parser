"""Constants for DISA exam parsing."""

import re

# Type code mappings (Swedish -> short code)
TYPE_CODES: dict[str, str] = {
    "Flervalsfråga": "mc1",
    "Flersvarsfråga": "mcn",
    "Sant/Falskt": "tf",
    "Essäfråga": "ess",
    "Essä": "ess",
    "Kortsvarsfråga": "short",
    "Matchning": "match",
    "Hotspot": "hot",
    "Dra och släpp i text": "drag",
    "Dra och släpp": "drag",
    "Dra och släpp i bild": "drag",
    "Dra och släpp text": "drag",
    "Textalternativ": "drop",
    "Textområde": "txt",
    "Textfält": "txt",
    "Textfält i bild": "txt",
    "Sifferfält": "txt",
    "Sammansatt": "ess",
    "Okänd": "unk",
}

# Course code mappings
COURSE_CODES: dict[str, str] = {
    "anatomi_och_histologi_1": "ah1",
    "anatomi_och_histologi_2": "ah2",
    "biokemi": "bio",
    "fysiologi": "fys",
    "genetik,_patologi,_pu,_farmakologi_och_konsultation": "gen",
    "infektion,_immunologi,_reumatologi_mfl": "inf",
    "klinisk_anatomi,_radiologi_och_konsultation": "kli",
    "molekylär_cellbiologi_och_utvecklingsbiologi": "mcb",
}

# Blacklisted files (merged/duplicate exams that don't add value)
BLACKLIST: set[str] = {
    "YZf9yLAXGlkpSbQ9GKlt_Tentor_med_svar.pdf",
    "7I3UGkJgSQcYE18EYYMR_Tentor_med_svar.pdf",
    "LCjrBjJiquEd9Vv2c24A_Tentor_med_svar.pdf",
    "tUEMcmS1CrYLJ1LWhpqG_Tentor_med_svar_.pdf",
}

# Question types recognized by the parser
QUESTION_TYPES: list[str] = [
    "Essä",
    "Essäfråga",
    "Flersvarsfråga",
    "Flervalsfråga",
    "Sant/Falskt",
    "Matchning",
    "Textområde",
    "Kortsvarsfråga",
    "Hotspot",
    "Dra och släpp i text",
    "Dra och släpp",
    "Dra och släpp i bild",
    "Dra och släpp text",
    "Textalternativ",
    "Sammansatt",
    "Textfält",
    "Textfält i bild",
    "Sifferfält",
]

# PDF format detection thresholds
FORMATS: dict[str, dict[str, int]] = {
    "TENTAMEN": {"X_QUESTION_NUMBER": 45, "X_OPTION": 70},
    "LPG-digital": {"X_QUESTION_NUMBER": 42, "X_OPTION": 62},
    "other": {"X_QUESTION_NUMBER": 45, "X_OPTION": 70},
}

# Answer markers
CORRECT_MARKERS: list[str] = ["✓", "✔", "\u2713", "\u2714", "●"]
INCORRECT_MARKERS: list[str] = ["✗", "✘", "\u2717", "\u2718", "○"]

# Color thresholds for answer detection
GREEN_THRESHOLD: tuple[float, float, float] = (0.3, 0.4, 0.2)

# Regex patterns
POINTS_PATTERN: re.Pattern = re.compile(r"Totalpoäng:\s*(\d+(?:[.,]\d+)?)")

# Swedish number words to digits
SWEDISH_NUMBERS: dict[str, int] = {
    "ett": 1, "en": 1, "två": 2, "tre": 3, "fyra": 4, "fem": 5,
    "sex": 6, "sju": 7, "åtta": 8, "nio": 9, "tio": 10,
}

# Pattern to detect expected answer count from question text
# Matches patterns like:
#   - "Välj två", "Markera tre", "Ange 2 svar"
#   - "Vilka två av...", "Vilka tre påståenden..."
#   - "Vilka påståenden" (plural implies multiple, defaults to 2)
#   - "två korrekta", "3 alternativ"
EXPECTED_ANSWERS_PATTERN: re.Pattern = re.compile(
    r"(?:välj|markera|ange|kryssa\s+för)\s+(?:de\s+)?(\d+|ett|en|två|tre|fyra|fem)"
    r"|vilka\s+(\d+|två|tre|fyra)"
    r"|vilka\s+(påståenden)"
    r"|(\d+|två|tre|fyra)\s+(?:korrekta|rätta)"
    r"|(\d+)\s*(?:svar|alternativ)",
    re.IGNORECASE
)

# Pattern for "one or more" answers (count unknown/variable)
# Matches: "Välj ett eller flera alternativ"
MULTIPLE_ANSWERS_PATTERN: re.Pattern = re.compile(
    r"välj\s+ett\s+eller\s+flera",
    re.IGNORECASE
)
