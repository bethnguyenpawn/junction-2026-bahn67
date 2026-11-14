"""Reads a dealer's note (Finnish, Swedish or English) into the facts that change a transport.

RULES, "Notes and changes of plan": a note can say when the car can be collected, when it must arrive, and what the
driver must bring or be allowed to drive; the world acts on it whether or not we read it. Days count from the day the
request arrives ("huomenna", a weekday name = that weekday 2 to 6 days later), digits are a 24-hour clock unless am/pm
follows, an hour in words is a working hour (9-17: "kahdelta" = 14:00, "halv tre" = 14:30), a correction counts and a
denied time ("ei klo 15", "not 3pm") does not.

How: words one typo away from a keyword are read as the keyword (the world misspells notes); then the note is read
sentence by sentence. Each sentence says what its time is about (ready, collect by, arrive by, opening hours), and a
later sentence or time corrects an earlier one. Scored against the revealed truth of 5,790 won orders with notes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config import DAY, HOUR


@dataclass(frozen=True)
class Facts:
    ready: int | None = None  # the car can be collected from this world minute (ready, or handed over once paid)
    deadline: int | None = None  # it must arrive by this minute (the earlier of this and the option's counts)
    delivery_close: int | None = None  # the delivery site closes at this minute of the day (a car after it is late)
    pickup_hours: tuple[int, int] | None = None  # the pickup site's real (opens, closes), minutes of the day
    plates: bool = False  # no plates: the driver fetches transfer plates on the way
    manual: bool = False  # manual gearbox: the driver needs a manual licence


NO_FACTS = Facts()

# --- Keywords that typos are corrected to (one letter added, dropped, changed or swapped; words of 5+ letters).
VOCABULARY = [
    "huomenna",
    "huomiseen",
    "ylihuomenna",
    "tänään",
    "morgon",
    "övermorgon",
    "tomorrow",
    "today",
    "maanantaina",
    "tiistaina",
    "keskiviikkona",
    "torstaina",
    "perjantaina",
    "maanantai",
    "tiistai",
    "keskiviikko",
    "torstai",
    "perjantai",
    "måndag",
    "tisdag",
    "onsdag",
    "torsdag",
    "fredag",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "valmis",
    "valmiina",
    "valmistuu",
    "noudettavissa",
    "haettavissa",
    "aikaisintaan",
    "viimeistään",
    "mennessä",
    "jälkeen",
    "alkaen",
    "perillä",
    "perille",
    "toimitus",
    "toimitettava",
    "destination",
    "deliver",
    "delivered",
    "arrive",
    "arrival",
    "tidigast",
    "senast",
    "framme",
    "framåt",
    "ready",
    "earliest",
    "latest",
    "manuaali",
    "manuaalia",
    "manuaalivaihteinen",
    "manual",
    "automaatti",
    "automaattivaihteinen",
    "kilvet",
    "kilpiä",
    "koekilvet",
    "siirtokilvet",
    "rekkarit",
    "rekkareita",
    "plates",
    "skyltar",
    "skyltarna",
    "provskyltar",
    "sulkee",
    "mottagning",
    "vastaanotto",
    "receiving",
    "haettava",
    "noudettava",
    "hämtas",
    "before",
    "collect",
    "correction",
    "korjaus",
    "luovutuksia",
    "puolta",
]
KNOWN = set(VOCABULARY) | {"plats", "platsen"}  # Swedish "place" is not "plates"

# --- What a sentence is about (role_of).
NO_PICKUP_BEFORE = re.compile(
    r"\b(no|not|ei|inte)\s+(pick ?up|nouto\w*|hämtning)|vasta sitten|saa hakea|financ|rahoitus"
)
CLOSES = re.compile(r"kiinni|\bclos|stäng|sulke|nobody|ei ketään|ingen|ei enää|no more|inga fler")
UNTIL = re.compile(r"\basti\b|\buntil\b|\btill\b|\bonly\b|\bvain\b|\d:?(?:een|ään|aan|iin)\b")
UNTIL_TIME = re.compile(r"\b(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?:?(?:een|ään|aan|iin)\b")  # "15:een" = until 15
FROM_TIME = re.compile(r"\b(?P<h>\d{1,2})(?:[:.](?P<m>\d{2}))?:?(?:stä|sta)\b")  # "9:stä" = from 9
PICKUP_BY = re.compile(
    r"\b(haettava|noudettava|nouto|haku|hakea|pick ?up|collect\w*|hämtas|hämta)\b.{0,20}?"
    r"\b(ennen|before|by|före|senast|viim\w*|no later than|latest)\b"
)
AT_DELIVERY = re.compile(
    r"perill|perille|destination|kohde|kohte|vastaanot|vasttaanot|mottag|receiving|toimitusosoite|framme"
)
ARRIVE = re.compile(
    r"perill|perille|toimit|destination|deliver|arriv|framme|leverer|leverans|på plats|vara där|asiakas noutaa"
    r"|asiakas tulee|customer (picks|collects|comes)|kunden hämtar|no later than"
)
READY = re.compile(
    r"valmi|noudettavissa|haettavissa|voi noutaa|voi hakea|auton saa|aikaisintaan|alkaen|jälkeen|ei ennen|ready"
    r"|earliest|not before|from|onward|available|klar|tidigast|från|framåt|kan hämtas|efter|inte före|maks|pays"
    r"|paid|payment|betal|luovut|handover|handed|release|utlämning"
)
OPEN_HOURS = re.compile(r"\bauki\b|aukiolo|\bopen|öppet|vastaanot|vasttaanot|mottag")
RANGE = re.compile(
    r"\b(?P<start>\d{1,2}(?:[:.]\d{2})?\s*(?:[ap]\.?m\.?)?)\s*-\s*(?P<end>\d{1,2}(?:[:.]\d{2})?\s*(?:[ap]\.?m\.?)?)"
)
DAY_RANGE = re.compile(r"\b(ma|ti|ke|to|pe|la|su|mon|tue|wed|thu|fri|sat|sun|mån|tis|ons|tors|fre)\.?\s*-\s*\w+")
CORRECTION = re.compile(r"^\s*(korjaus|eikun|ei kun|tai siis|siis|sorry|correction|i mean|rättelse|förlåt|alltså)")

# --- Days.
DAY_WORDS = [
    (re.compile(r"\bylihuom\w*|\b(?:i\s?)?övermorgon|\b(?:the\s)?day after tomorrow"), 2),
    (re.compile(r"\bhuom(?:en|ise)\w*|\bi\s?morgon|\bimorgon|\btomorrow|\btmrw|\btmr\b"), 1),
    (re.compile(r"\btänään|\btännään|\btanaan|\bidag|\bi dag|\btoday"), 0),
]
WEEKDAYS = [  # Monday = 0
    r"maanantai\w*|måndag\w*|monday|mon|mån",
    r"tiistai\w*|tisdag\w*|tuesday|tues?|tis",
    r"keskiviik\w*|onsdag\w*|wednesday|wed|ons",
    r"torstai\w*|torsdag\w*|thursday|thu(?:rs?)?|tors",
    r"perjantai\w*|fredag\w*|friday|fri|fre",
    r"lauantai\w*|lördag\w*|saturday|sat|lör",
    r"sunnuntai\w*|söndag\w*|sunday|sun|sön",
]
WEEKDAY = re.compile("|".join(f"(?P<w{i}>\\b(?:{forms})\\b)" for i, forms in enumerate(WEEKDAYS)))
WEEKDAY_FI = re.compile(  # Finnish short forms ("to.", "pe"): only in Finnish notes
    "|".join(f"(?P<w{i}>\\b{short}\\b)" for i, short in enumerate(["ma", "ti", "ke", "to", "pe", "la", "su"]))
)

# --- Times.
HOUR_WORDS = [  # the working hour with that number (9-17); 11 and 12 first ("kahdeltatoista" is not "kahdelta")
    (11, r"(?:yksi|yhde|yhte)\w*toista|elva|eleven"),
    (12, r"(?:kaksi|kahde|kahte)\w*toista|tolv|twelve|noon|keskipäiv\w*"),
    (9, r"yhdeksä\w*|nio|nine"),
    (10, r"kymmene\w*|tio|ten"),
    (13, r"yhdeltä|yhteen|yhdestä|yhden|yksi|ett|one"),
    (14, r"kahdelta|kahteen|kahdesta|kahden|kaksi|två|two"),
    (15, r"kolmelta|kolmeen|kolmesta|kolmen|kolme|tre|three"),
    (16, r"neljältä|neljään|neljästä|neljän|neljä|fyra|four"),
    (17, r"viideltä|viiteen|viidestä|viiden|viittä|viisi|fem|five"),
]
WORD_HOUR = re.compile(
    r"(?P<half>\b(?:puoli|puolta|halv|half)\s+)?(?P<mark>\b(?:klo|kl\.?|klockan|kello|at|by)\s+)?\b(?:"
    + "|".join(f"(?P<h{hour}>{forms})" for hour, forms in HOUR_WORDS)
    + r")\b"
)
INFLECTED = re.compile(r"(ltä|lta|een|ään|stä|sta|toista|noon|keskipäiv\w*)$")  # "kahdelta", "viiteen": a time
CLOCK = re.compile(
    r"(?P<mark>\b(?:klo|kl|klockan|kello|at)\.?\s*|@\s*)?\b(?P<h>\d{1,2})(?:[:.]?(?P<m>\d{2}))?(?!\d)"
    r"\s*(?P<ampm>[ap]\.?m\b\.?)?"
)
BARE_BEFORE = re.compile(r"(ennen|before|före|by|from|från|efter|after|until|till|kello|na|morgon|tomorrow)\s*$")
BARE_AFTER = re.compile(r"\s*(jälkeen|alkaen|mennessä|asti|o'clock|och framåt|onwards?)")
NOT_A_TIME = re.compile(r"\s*(min|km|%|kpl|€|eur|h\b|sarja|set|st\b)")
DENY = re.compile(r"(\bei|\bnot|\binte|\bnej|\bno)\s*(klo|kl\.?|at)?\s*\(?\s*$")

PLATES = re.compile(r"kilp|kilv|plates|skylt|rekkar|rekisteristä|avregistr|deregist")
MANUAL = re.compile(r"manuaali|manual|manuell|käsivaiht|stick ?shift")
AUTOMATIC = re.compile(r"automaat|automat")

ABBREVIATIONS = {"viim", "klo", "kl", "n", "ma", "ti", "ke", "to", "pe", "la", "su", "huom", "esim", "nro", "puh"}


def read(note: dict | None, arrived_at: int) -> Facts:
    """The facts in a note, as world minutes; arrived_at is when the request arrived (days count from its day)."""
    if not note or not note.get("text"):
        return NO_FACTS
    text = corrected(re.sub(r"[–—‒−]", "-", note["text"].lower()))
    finnish = note.get("language") == "fi"
    today = arrived_at // DAY
    found: dict[str, tuple[int | None, int | None]] = {}  # role -> (days after today, minute of the day)
    role = None
    for sentence in sentences(text):
        correction = CORRECTION.match(sentence)  # "korjaus: klo 10" / "korjaus: maanantaina" corrects the last
        role = role if correction else role_of(sentence)
        if role != "delivery_close" and not AT_DELIVERY.search(sentence):
            stated_hours = role == "pickup_hours" or RANGE.search(sentence) or UNTIL_TIME.search(sentence)
            hours = opening(sentence) if stated_hours else None
            if hours is not None:
                found["pickup_hours"] = hours  # "Klo 9-14.30 nouto onnistuu", "Nouto ennen klo 14.30"
        if role in (None, "pickup_hours"):
            continue
        if role == "delivery_close":
            day, minute = None, closing(sentence)
        else:
            day, minute = moment(DAY_RANGE.sub(" ", RANGE.sub(" ", sentence)), today, finnish)  # hours: no moment
        if correction and role in found:
            day, minute = (found[role][0] if day is None else day), (found[role][1] if minute is None else minute)
        if minute is not None:
            found[role] = (day, minute)  # a later sentence corrects an earlier one
    when = {
        role: (today + (day or 0)) * DAY + minute for role, (day, minute) in found.items() if role != "pickup_hours"
    }
    return Facts(
        ready=when.get("ready"),
        deadline=when.get("deadline"),
        delivery_close=found["delivery_close"][1] if "delivery_close" in found else None,
        pickup_hours=found.get("pickup_hours"),
        plates=bool(PLATES.search(text)),
        manual=stated(MANUAL, text) or denied(AUTOMATIC, text),
    )


def due(facts: Facts, deadline: int) -> int:
    """The latest delivery that counts as on time: the option's deadline, the note's, and the delivery site's
    closing time on that day (a car left at a closed site counts when it next opens)."""
    if facts.deadline is not None:
        deadline = min(deadline, facts.deadline)
    if facts.delivery_close is not None:
        deadline = min(deadline, deadline // DAY * DAY + facts.delivery_close)
    return deadline


def corrected(text: str) -> str:
    """The text with each word one typo away from a keyword replaced by that keyword."""

    def fix(match: re.Match) -> str:
        word = match.group()
        if len(word) < 5 or word in KNOWN:
            return word
        return next((known for known in VOCABULARY if one_typo(word, known)), word)

    return re.sub(r"[a-zåäö]+", fix, text)


def one_typo(a: str, b: str) -> bool:
    """True if b is a with one letter added, dropped, changed, or two neighbours swapped."""
    if abs(len(a) - len(b)) > 1 or a == b:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    if len(a) == len(b):
        return a[i + 1 :] == b[i + 1 :] or (a[i + 2 :] == b[i + 2 :] and a[i : i + 2] == b[i : i + 2][::-1])
    return a[i + 1 :] == b[i:] if len(a) > len(b) else a[i:] == b[i + 1 :]


def sentences(text: str) -> list[str]:
    """Splits at sentence ends and at " / " (notes repeat themselves in two languages), not after abbreviations
    ("viim.", "ma.") or inside a clock time ("14.30")."""
    out, start = [], 0
    for match in re.finditer(r"[.!?;]+\s+|\s/\s|\n", text):
        before = text[start : match.start()].split()
        if match.group().startswith(".") and before and before[-1].strip("(") in ABBREVIATIONS:
            continue
        out.append(text[start : match.start()])
        start = match.end()
    out.append(text[start:])
    return [s for s in out if s.strip()]


def role_of(sentence: str) -> str | None:
    """ready, deadline, delivery_close, pickup_hours, or None (nothing for us)."""
    if NO_PICKUP_BEFORE.search(sentence):
        return "ready"
    hours = CLOSES.search(sentence) or (
        OPEN_HOURS.search(sentence) and (RANGE.search(sentence) or UNTIL.search(sentence))
    )
    if AT_DELIVERY.search(sentence) and (hours or UNTIL.search(sentence) or RANGE.search(sentence)):
        return "delivery_close"
    if hours or PICKUP_BY.search(sentence):
        return "pickup_hours"
    if ARRIVE.search(sentence):
        return "deadline"
    if READY.search(sentence):
        return "ready"
    return None


def closing(sentence: str) -> int | None:
    """The closing minute of the day in "open 8-16" or "closes at 16:30" / "kiinni klo 16 jälkeen"."""
    ranges = list(RANGE.finditer(sentence))
    until = list(UNTIL_TIME.finditer(sentence))
    if until:
        return int(until[-1]["h"]) * HOUR + int(until[-1]["m"] or 0)
    if ranges:
        found = times(ranges[-1]["end"] if ranges[-1]["end"][0].isdigit() else "", marked=True)
        return found[-1][1] if found else None
    sentence = DAY_RANGE.sub(" ", sentence)
    found = [minute for start, minute in sorted(times(sentence)) if not DENY.search(sentence[:start])]
    return found[-1] if found else None


def opening(sentence: str) -> tuple[int, int] | None:
    """The pickup site's (opens, closes) in "auki 9-15.30" / "Nouto ennen klo 14.30" (opens unknown: 0)."""
    since, until = FROM_TIME.search(sentence), list(UNTIL_TIME.finditer(sentence))
    if since and until:
        return int(since["h"]) * HOUR + int(since["m"] or 0), int(until[-1]["h"]) * HOUR + int(until[-1]["m"] or 0)
    ranges = list(RANGE.finditer(sentence))
    if ranges:
        opens = times(ranges[-1]["start"], marked=True)
        closes = times(ranges[-1]["end"], marked=True)
        if opens and closes and opens[-1][1] < closes[-1][1]:
            return opens[-1][1], closes[-1][1]
    close = closing(sentence)
    return None if close is None else (0, close)


def open_interval(window: dict, hours: tuple[int, int], earliest: int, lead: int = 2 * HOUR) -> dict:
    """The first weekday interval of the pickup site's real hours inside the window that a driver can still reach
    (closing at least `lead` after `earliest`); the window itself if there is none. A single interval, because a
    driver plans by the site's stated hours and would come after the real closing on any other day."""
    opens, closes = hours
    start = max(window["from"], earliest)
    for day in range(start // DAY, window["to"] // DAY + 1):
        if day % 7 >= 5:
            continue
        begin, end = max(window["from"], day * DAY + opens), min(window["to"], day * DAY + closes)
        if end - max(begin, earliest) >= min(lead, closes - opens) and end > earliest + lead // 4:
            return {"from": begin, "to": end}
    return window


def stated(pattern: re.Pattern, text: str) -> bool:
    return any(not DENY.search(text[: m.start()]) for m in pattern.finditer(text))


def denied(pattern: re.Pattern, text: str) -> bool:
    return any(DENY.search(text[: m.start()]) for m in pattern.finditer(text))


def moment(sentence: str, today: int, finnish: bool) -> tuple[int | None, int | None]:
    """The last day (days after today) and the last time (minute of the day) the sentence states and does not
    deny; None where it states none."""
    spans = [(m.start(), m.end(), offset) for pattern, offset in DAY_WORDS for m in pattern.finditer(sentence)]
    for pattern in (WEEKDAY, WEEKDAY_FI) if finnish else (WEEKDAY,):
        for m in pattern.finditer(sentence):
            weekday = int(next(k for k, v in m.groupdict().items() if v)[1:])
            ahead = (weekday - today) % 7
            spans.append((m.start(), m.end(), ahead if ahead >= 2 else ahead + 7))
    day = None
    for start, end, offset in sorted(spans):
        inside = any(s <= start and end <= e and (s, e) != (start, end) for s, e, _ in spans)  # "tomorrow" in
        if not inside and not DENY.search(sentence[:start]):  # "the day after tomorrow"
            day = offset
    minute = None
    for start, value in sorted(times(sentence)):
        if not DENY.search(sentence[:start]):
            minute = value
    return day, minute


def times(sentence: str, marked: bool = False) -> list[tuple[int, int]]:
    """(position, minute of the day) of every clock time: digits with a marker, hh:mm, am/pm, or hour words.
    marked: the sentence is known to be a time (the end of a range)."""
    out = []
    for m in CLOCK.finditer(sentence):
        hour, minute = int(m["h"]), int(m["m"] or 0)
        if m["ampm"]:
            hour = hour % 12 + (12 if m["ampm"].startswith("p") else 0)
        elif not (marked or m["mark"]) and (m["m"] is None or ":" not in m.group() and "." not in m.group()):
            # a bare number ("torstaina 12 jälkeen") counts only next to a day or a time word
            if not (BARE_BEFORE.search(sentence[: m.start()]) or BARE_AFTER.match(sentence[m.end() :])):
                continue
            if NOT_A_TIME.match(sentence[m.end() :]):
                continue
        if hour > 24 or minute > 59:
            continue
        out.append((m.start(), hour * HOUR + minute))
    for m in WORD_HOUR.finditer(sentence):
        hour = next(int(k[1:]) for k, v in m.groupdict().items() if k[0] == "h" and k[1:].isdigit() and v)
        word = m.group(0).split()[-1]
        if not (m["half"] or m["mark"] or INFLECTED.search(word) or BARE_AFTER.match(sentence[m.end() :])):
            continue
        out.append((m.start(), hour * HOUR - (30 if m["half"] else 0)))
    return out
