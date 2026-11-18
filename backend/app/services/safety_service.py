"""Medical safety layer - deterministic rules that do NOT depend on the AI.

1. screen_user_message(): runs on every user message BEFORE the AI is called.
   Emergency warning signs short-circuit the conversation with fixed guidance
   (no AI call, no further questions, no delay).
2. filter_ai_reply(): runs on every AI reply. Removes medication dosing and
   diagnostic certainty that the system prompt forbids, in case the model slips.
3. enforce_report_rules(): validates generated reports (urgency floor, no
   "confirmed" diagnoses, size limits).

IMPORTANT: These rules are an engineering safety net written without clinical
review. They are English-only, keyword-based, and WILL miss some emergencies
and flag some non-emergencies. They must be reviewed and extended by qualified
clinicians before HealthAI is used by real patients.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

Level = Literal["emergency", "urgent"]

# Words that, shortly before a match, mean the user is denying the symptom
# ("no chest pain", "I don't have trouble breathing").
_NEGATION = re.compile(
    r"\b(no|not|never|without|denies|deny|don'?t|doesn'?t|didn'?t|haven'?t|hasn'?t|isn'?t|aren'?t|wasn'?t|nor|free of)\b[^.!?;,]{0,25}$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Rule:
    category: str
    level: Level
    label: str  # shown in reports, e.g. "Possible heart-related warning signs"
    patterns: tuple[str, ...]


RULES: tuple[Rule, ...] = (
    Rule(
        "self_harm",
        "emergency",
        "Thoughts of suicide or self-harm",
        (
            r"\bsuicid",
            r"\bkill(ing)? my ?self\b",
            r"\bend (it all|my life)\b",
            r"\bwant(ing)? to die\b",
            r"\b(hurt|harm|cut)(ing)? my ?self\b",
            r"\bself[- ]harm",
            r"\bno reason to live\b",
        ),
    ),
    Rule(
        "cardiac",
        "emergency",
        "Possible heart-related warning signs",
        (
            r"\bheart attack\b",
            r"\bchest (pain|tightness|pressure)\b[^.!?]{0,60}\b(arm|jaw|neck|back|sweat|sweating|breath|breathless|faint|dizzy|nause)",
            r"\b(arm|jaw)\b[^.!?]{0,60}\bchest (pain|tightness|pressure)\b",
            r"\b(crushing|severe|sudden) chest (pain|pressure|tightness)\b",
            r"\btight(ness)? (pain )?in (my )?chest\b[^.!?]{0,60}\b(arm|jaw|sweat|breath)",
            r"\bchest\b[^.!?]{0,30}\b(tight|pain)\b[^.!?]{0,40}\bleft arm\b",
        ),
    ),
    Rule(
        "breathing",
        "emergency",
        "Severe breathing difficulty",
        (
            r"\b(can'?t|cannot|can not|unable to|struggling to|hard to) breathe\b",
            r"\bcan'?t (catch|get) (my|a) breath\b",
            r"\b(severe|extreme) (shortness of breath|breathlessness)\b",
            r"\bchoking\b",
            r"\b(lips|face|fingers) (are |is )?(turning )?(blue|grey|gray)\b",
            r"\bgasping\b",
        ),
    ),
    Rule(
        "stroke",
        "emergency",
        "Possible stroke warning signs",
        (
            r"\bstroke\b",
            r"\bface (is )?(drooping|droops|droop)\b|\bdrooping face\b|\bface droop",
            r"\bslurred speech\b|\bslurring (my )?words\b|\bspeech is slurred\b",
            r"\b(sudden|suddenly)\b[^.!?]{0,30}\b(numb|weak|weakness|paraly)[^.!?]{0,30}\b(one side|left side|right side|arm|leg|face)\b",
            r"\b(can'?t|cannot) (move|lift|feel) (my )?(arm|leg|face)\b",
        ),
    ),
    Rule(
        "neuro",
        "emergency",
        "Serious neurological warning signs",
        (
            r"\bworst headache (of my life|ever|i'?ve ever)\b",
            r"\bthunderclap headache\b",
            r"\b(seizure|seizing|convulsion|convulsing|having a fit)\b",
            r"\b(unconscious|unresponsive|won'?t wake up|not waking up|passed out and)\b",
            r"\bstiff neck\b[^.!?]{0,60}\b(fever|rash|light)\b|\bfever\b[^.!?]{0,60}\bstiff neck\b",
        ),
    ),
    Rule(
        "bleeding",
        "emergency",
        "Severe bleeding",
        (
            r"\b(severe|heavy|uncontrolled|lots of|a lot of) bleeding\b",
            r"\bbleeding (won'?t|will not|doesn'?t|does not) stop\b",
            r"\b(vomiting|throwing up|coughing up|coughing) blood\b",
        ),
    ),
    Rule(
        "allergy",
        "emergency",
        "Possible severe allergic reaction",
        (
            r"\banaphyla",
            r"\bthroat (is )?(closing|swelling|swollen|tight)\b",
            r"\b(tongue|lips?) (is |are )?(swelling|swollen)\b",
        ),
    ),
    Rule(
        "poisoning",
        "emergency",
        "Possible poisoning or overdose",
        (
            r"\boverdos",
            r"\btook too many (pills|tablets)\b",
            r"\b(swallowed|drank|ate) (poison|bleach|pesticide|rat poison)\b",
            r"\bpoison(ed|ing)\b",
        ),
    ),
    Rule(
        "pregnancy",
        "emergency",
        "Pregnancy-related warning signs",
        (
            r"\bpregnan[^.!?]{0,60}\b(bleeding|severe pain|heavy pain|fluid leaking|baby (isn'?t|is not|stopped) moving)",
            r"\b(bleeding|severe pain)\b[^.!?]{0,60}\bpregnan",
        ),
    ),
    # --- urgent: AI continues, but the report can never be rated below "urgent" ---
    Rule(
        "urgent_gi_bleed",
        "urgent",
        "Possible internal bleeding signs",
        (r"\b(black|tarry) (stool|stools|poo|poop)\b", r"\bblood in (my )?(stool|stools|urine|poo|pee)\b"),
    ),
    Rule(
        "urgent_high_fever",
        "urgent",
        "Very high or persistent fever",
        (r"\bfever\b[^.!?]{0,40}\b(10[4-9]|4[0-2])(\.\d)?\s?(°|deg|degrees)?\s?(f|c)?\b", r"\bfever (for|since) (a week|\d+ days)\b"),
    ),
    Rule(
        "urgent_abdominal",
        "urgent",
        "Severe abdominal pain",
        (r"\b(severe|unbearable|excruciating|worst) (stomach|abdominal|belly|tummy) pain\b",),
    ),
    Rule(
        "urgent_head_injury",
        "urgent",
        "Head injury",
        (r"\b(hit|banged|injured|hurt) (my )?head\b", r"\bhead injury\b", r"\bconcussion\b"),
    ),
)

_COMPILED = tuple((rule, tuple(re.compile(p, re.IGNORECASE) for p in rule.patterns)) for rule in RULES)


@dataclass
class SafetyResult:
    level: Level | None = None
    categories: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    @property
    def is_emergency(self) -> bool:
        return self.level == "emergency"


def _negated(text: str, start: int) -> bool:
    return bool(_NEGATION.search(text[max(0, start - 40) : start]))


def screen_user_message(text: str) -> SafetyResult:
    """Deterministic red-flag screen. Emergency outranks urgent."""
    normalized = re.sub(r"[’`]", "'", text)
    result = SafetyResult()
    for rule, patterns in _COMPILED:
        for pattern in patterns:
            match = pattern.search(normalized)
            if match and not _negated(normalized, match.start()):
                result.categories.append(rule.category)
                result.labels.append(rule.label)
                if rule.level == "emergency":
                    result.level = "emergency"
                elif result.level is None:
                    result.level = "urgent"
                break
    return result


# ---------------- fixed emergency responses (no AI involved) ----------------

_GENERIC_EMERGENCY = (
    "What you've described can be a sign of a medical emergency.\n\n"
    "Please call your local emergency number or go to the nearest emergency department now. "
    "Don't wait to see if it gets better, and don't drive yourself if you can avoid it. "
    "If someone is with you, tell them what's happening.\n\n"
    "I've stopped asking questions so you can get help right away. HealthAI can't assess emergencies."
)

_SELF_HARM = (
    "I'm really sorry you're feeling this way. You deserve support right now, and you don't have to go through this alone.\n\n"
    "If you might act on these thoughts or are in danger, please call your local emergency number now or go to the nearest emergency department.\n\n"
    "If you can, reach out to someone you trust and let them know how you're feeling, or contact a local crisis or "
    "mental-health helpline. Talking to someone can help.\n\n"
    "HealthAI isn't able to provide crisis support, so I've paused this conversation so you can reach someone who can."
)


def emergency_reply(result: SafetyResult) -> str:
    return _SELF_HARM if "self_harm" in result.categories else _GENERIC_EMERGENCY


def emergency_report_fields(result: SafetyResult) -> dict:
    """Report content for an emergency stop, built from rules, not the AI."""
    return {
        "symptoms": result.labels or ["Emergency warning signs"],
        "duration": "Not assessed",
        "severity": "Not assessed: emergency guidance was given immediately",
        "additional_info": [],
        "possible_explanations": [],
        "warning_signs": result.labels,
        "next_steps": [
            "Call your local emergency number or go to the nearest emergency department now",
            "Do not drive yourself if you can avoid it",
            "If someone is with you, tell them what is happening",
        ],
        "urgency_level": "emergency",
        "urgency_reason": "You described warning signs that need immediate emergency care.",
    }


# ---------------- AI output filter ----------------

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
_DOSING = re.compile(
    r"\b\d+(\.\d+)?\s?(mg|mcg|µg|ml|milligrams?|micrograms?|tablets?|pills?|capsules?|puffs?|drops?)\b"
    r"|\b(take|taking|use|try)\s+(\w+\s+){0,2}(ibuprofen|paracetamol|acetaminophen|aspirin|antibiotics?|amoxicillin|"
    r"azithromycin|naproxen|diclofenac|codeine|tramadol|cetirizine|loratadine|omeprazole|pantoprazole|metformin|"
    r"prednisolone|steroids?|dolo|crocin|combiflam)\b",
    re.IGNORECASE,
)
_CERTAINTY = re.compile(
    r"\byou (definitely|certainly|clearly) have\b|\bthis is (definitely|certainly|clearly)\b|\bi can confirm\b|"
    r"\b(my|the) diagnosis is\b|\bi('?m| am) diagnosing\b|\byou('?ve| have) been diagnosed\b|\bthere'?s nothing to worry about\b|"
    r"\bi('?ve| have) ruled out\b",
    re.IGNORECASE,
)

MEDICATION_NOTE = "I can't recommend specific medicines or doses. A doctor or pharmacist can advise you on treatment."


@dataclass
class FilterResult:
    text: str
    removed_dosing: bool = False
    removed_certainty: bool = False


def filter_ai_reply(text: str) -> FilterResult:
    sentences = [s for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]
    kept: list[str] = []
    dosing = certainty = False
    for s in sentences:
        if _DOSING.search(s):
            dosing = True
            continue
        if _CERTAINTY.search(s):
            certainty = True
            continue
        kept.append(s.strip())
    out = " ".join(kept).strip()
    if dosing:
        out = f"{out} {MEDICATION_NOTE}".strip()
    if not out:
        out = "I'm not able to answer that safely. Could you tell me a bit more about your symptoms?"
    return FilterResult(out, dosing, certainty)


# ---------------- report rules ----------------

_FORBIDDEN_IN_EXPLANATION = re.compile(r"\b(confirmed|definitely|certainly|diagnosed)\b", re.IGNORECASE)


def enforce_report_rules(report: dict, urgency_floor: str | None) -> dict:
    """Server-side checks on an AI-generated report before it is stored."""
    from app.schemas.health import URGENCY_ORDER

    if urgency_floor and URGENCY_ORDER[report["urgency_level"]] < URGENCY_ORDER[urgency_floor]:
        report["urgency_level"] = urgency_floor
        report["urgency_reason"] = (
            "Based on warning signs you mentioned, please get medical care promptly. " + report.get("urgency_reason", "")
        ).strip()

    cleaned = []
    for exp in report.get("possible_explanations", [])[:5]:
        name = _FORBIDDEN_IN_EXPLANATION.sub("", exp["name"]).strip()
        why = filter_ai_reply(exp["why"]).text if _DOSING.search(exp["why"]) else exp["why"]
        if name:
            cleaned.append({"name": name[:120], "why": why[:600]})
    report["possible_explanations"] = cleaned
    report["next_steps"] = [filter_ai_reply(s).text if _DOSING.search(s) else s for s in report.get("next_steps", [])][:8]
    for key in ("symptoms", "additional_info", "warning_signs"):
        report[key] = [str(x)[:300] for x in report.get(key, [])][:10]
    return report
