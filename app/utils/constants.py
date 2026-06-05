from typing import Dict, List

# =========================
# API-Konstanten
# =========================
CR_BASE = "https://api.crossref.org"

JOURNAL_ISSN: Dict[str, str] = {
    "The Leadership Quarterly": "1048-9843",
    "Human Relations": "0018-7267",
    "Organization Studies": "0170-8406",
    "Organizational Research Methods": "1094-4281",
    "Journal of Leadership and Organizational Studies": "1939-7089",
    "Journal of Organizational Behavior": "0894-3796",
    "Journal of Management Studies": "0022-2380",
    "Personnel Psychology": "0031-5826",
    "European Management Review": "1740-4754",
    "Organization Science": "1047-7039",
    "Management Science": "0025-1909",
    "Academy of Management Journal": "0001-4273",
    "Zeitschrift für Arbeits- und Organisationspsychologie": "0932-4089",
    "Journal of Applied Psychology": "0021-9010",
    "Journal of Personality and Social Psychology": "0022-3514",
    "Journal of Occupational Health Psychology": "1076-8998",
    "Journal of Management": "0149-2063",
    "Strategic Management Journal": "0143-2095",

    # NEU:
    "Science": "0036-8075",
    "Nature": "0028-0836",
    "Administrative Science Quarterly": "0001-8392",
    "Management Teaching Review": "2379-2981",
}

ALT_ISSN: Dict[str, List[str]] = {
    "Journal of Applied Psychology": ["1939-1854"],
    "Journal of Personality and Social Psychology": ["1939-1315"],
    "Journal of Leadership and Organizational Studies": ["1939-7089"],
    "Journal of Occupational Health Psychology": ["1939-1307"],
    "Journal of Management": ["1557-1211"],
    "Human Relations": ["1741-282X"],
    "Personnel Psychology": ["1744-6570"],
    "Journal of Management Studies": ["1467-6486"],
    "European Management Review": ["1740-4762"],
    "Academy of Management Journal": ["1948-0989"],
    "The Leadership Quarterly": ["1873-3409"],
    "Organizational Research Methods": ["1552-7425"],

    # NEU:
    "Science": ["1095-9203"],
    "Nature": ["1476-4687"],
    "Administrative Science Quarterly": ["1930-3815"],
}

# =========================
# Text/Trend Utilities (Relevance & Intelligence)
# =========================
STOPWORDS = set("""
a an and are as at be by for from has have in is it its of on or that the to was were will with
about above after again against all am among an any are aren't as at because been before being
below between both but by can't cannot could couldn't did didn't do does doesn't doing don't down
during each few for from further had hadn't has hasn't have haven't having he he'd he'll he's her
here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's
its itself just me more most mustn't my myself no nor not of off on once only or other ought our
ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than
that that's the their theirs them themselves then there there's these they they'd they'll they're
they've this those through to too under until up very was wasn't we we'd we'll we're we've were
weren't what what's when when's where where's which while who who's whom why why's with won't would
wouldn't you you'd you'll you're you've your yours yourself yourselves
der die das und ist im in den von mit auf als auch bei für des dem ein eine einer einem einen
wie zu zur zum aus über unter nach vor nicht kein keine einer eines wurden wird werden
""".split())

# --- Excel-Engine Detection (xlsxwriter / openpyxl) ---
_HAS_XLSXWRITER = False
_HAS_OPENPYXL = False
try: import xlsxwriter; _HAS_XLSXWRITER = True
except Exception: pass
try: import openpyxl; _HAS_OPENPYXL = True
except Exception: pass