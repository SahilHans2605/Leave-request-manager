from datetime import date, timedelta
from typing import Dict, Any

# Optional: TextBlob sentiment (nice-to-have). If not installed, code still works.
try:
    from textblob import TextBlob  # pip install textblob
except Exception:
    TextBlob = None


# -----------------------------
# Helpers
# -----------------------------
def business_days(start: date, end: date) -> int:
    """Count weekdays (Mon–Fri) inclusive. Returns 0 if invalid range."""
    if not start or not end or end < start:
        return 0
    days = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return days


def capacity_after_leave(team_size: int, people_on_leave: int) -> float:
    """Capacity = available/total after including this leave."""
    if team_size <= 0:
        return 1.0
    available = max(team_size - people_on_leave, 0)
    return available / team_size


# -----------------------------
# Reason (Sentiment + Intent) Analysis
# -----------------------------
def analyze_reason(reason: str) -> Dict[str, Any]:
    """
    Returns:
      category: FRIVOLOUS / VALID / NEUTRAL
      note: short explanation
      polarity: -1..1 (if TextBlob available else 0)
    """
    if not reason or not reason.strip():
        return {"category": "NEUTRAL", "note": "No reason provided", "polarity": 0.0}

    text = reason.strip().lower()

    # Simple intent keywords (hackathon-smart)
    frivolous_keywords = [
        "not in mood", "no mood", "bored", "chill", "party", "hangout",
        "just tired", "tired", "dont feel like", "don't feel like", "lazy",
        "want a break", "need break", "movie", "shopping", "gaming",
    ]

    valid_keywords = [
        "hospital", "admit", "admitted", "sick", "ill", "fever", "doctor",
        "emergency", "accident", "injury", "medical", "checkup",
        "mother", "mom", "father", "dad", "grandmother", "grandfather",
        "funeral", "death", "passed away", "bereavement",
    ]

    # Keyword match first (most reliable)
    for kw in valid_keywords:
        if kw in text:
            return {"category": "VALID", "note": f"Matched valid keyword: '{kw}'", "polarity": 0.0}

    for kw in frivolous_keywords:
        if kw in text:
            return {"category": "FRIVOLOUS", "note": f"Matched casual keyword: '{kw}'", "polarity": 0.0}

    # Sentiment fallback (only if TextBlob exists)
    polarity = 0.0
    if TextBlob is not None:
        try:
            polarity = float(TextBlob(text).sentiment.polarity)  # -1..1
        except Exception:
            polarity = 0.0

    # Interpretation:
    # Very negative sentiment often correlates with distress -> treat as VALID-ish
    # Very positive sentiment often correlates with casual excitement -> treat as FRIVOLOUS-ish
    if polarity <= -0.50:
        return {"category": "VALID", "note": "Very negative sentiment → likely genuine", "polarity": polarity}
    if polarity >= 0.50:
        return {"category": "FRIVOLOUS", "note": "Very positive sentiment → likely casual", "polarity": polarity}

    return {"category": "NEUTRAL", "note": "No strong signal", "polarity": polarity}


# -----------------------------
# Risk components (0..100 total)
# Capacity: 0..40
# Deadlines: 0..40
# Duration: 0..20
# -----------------------------
def capacity_score(capacity_after: float, min_threshold: float) -> int:
    """
    0..40
    - if capacity falls below min_threshold => 40
    - if capacity >= 90% => 0
    - otherwise linearly scale between 90% and min_threshold
    """
    if capacity_after < min_threshold:
        return 40
    if capacity_after >= 0.90:
        return 0

    span = 0.90 - min_threshold
    if span <= 0:
        return 10  # fallback
    ratio = (0.90 - capacity_after) / span
    return int(max(0, min(40, ratio * 40)))


def deadline_score(overlapping_deadlines: int, near_deadlines: int) -> int:
    """
    0..40
    - overlapping deadlines are heavy risk
    - near deadlines are medium risk
    """
    score = 0
    score += min(overlapping_deadlines * 25, 40)
    score += min(near_deadlines * 10, 20)
    return int(min(score, 40))


def duration_score(days_requested: int) -> int:
    """0..20 based on leave length."""
    if days_requested <= 1:
        return 2
    if days_requested <= 3:
        return 8
    if days_requested <= 5:
        return 14
    return 20


def risk_level_from_score(risk: int) -> str:
    """LOW / MED / HIGH / CRIT."""
    if risk >= 85:
        return "CRIT"
    if risk >= 70:
        return "HIGH"
    if risk >= 35:
        return "MED"
    return "LOW"


# -----------------------------
# Main evaluator
# -----------------------------
def evaluate_leave(
    balance: float,
    days_requested: int,
    team_size: int,
    current_approved_leaves: int,
    min_capacity: float,
    overlapping_deadlines: int,   # ESCALATE-policy overlaps
    near_deadlines: int,          # ESCALATE-policy near-window deadlines
    hard_block_overlaps: int,     # HARD_BLOCK overlaps
    reason: str = "",
) -> Dict[str, Any]:
    """
    Always returns:
    - decision: REJECT / AUTO_APPROVE / ESCALATE
    - risk: 0..100
    - level: LOW/MED/HIGH/CRIT
    - reasons: list[str]
    - capacity_after: float
    - components: {capacity, deadlines, duration}
    - reason_tag: FRIVOLOUS/VALID/NEUTRAL + note
    """

    # Safe base ensures templates never crash
    safe_base: Dict[str, Any] = {
        "decision": "ESCALATE",
        "risk": 0,
        "level": "LOW",
        "reasons": [],
        "capacity_after": 1.0,
        "components": {"capacity": 0, "deadlines": 0, "duration": 0},
        "reason_tag": {"category": "NEUTRAL", "note": "No signal", "polarity": 0.0},
    }

    # ---- Hard rejection rules ----
    if days_requested <= 0:
        safe_base.update({
            "decision": "REJECT",
            "risk": 100,
            "level": "CRIT",
            "reasons": ["Invalid date range or 0 working days."],
        })
        return safe_base

    if balance < days_requested:
        safe_base.update({
            "decision": "REJECT",
            "risk": 100,
            "level": "CRIT",
            "reasons": [f"Insufficient leave balance. Required={days_requested}, Available={balance}"],
        })
        return safe_base

    # HARD_BLOCK overlap => always reject (policy based)
    if hard_block_overlaps > 0:
        safe_base.update({
            "decision": "REJECT",
            "risk": 100,
            "level": "CRIT",
            "reasons": [f"Leave overlaps {hard_block_overlaps} HARD_BLOCK deadline(s). Policy: Auto-Reject."],
        })
        return safe_base

    # STRICT capacity gate (you asked for auto-reject based on team strength danger level)
    cap_after_gate = capacity_after_leave(team_size, current_approved_leaves + 1)
    if cap_after_gate < min_capacity:
        safe_base.update({
            "decision": "REJECT",
            "risk": 100,
            "level": "CRIT",
            "capacity_after": cap_after_gate,
            "reasons": [
                f"Auto-rejected: Team capacity would drop to {cap_after_gate:.0%}, "
                f"below minimum threshold {min_capacity:.0%}."
            ],
        })
        return safe_base

    # ---- Reason Analysis (sentiment + intent) ----
    reason_tag = analyze_reason(reason)
    safe_base["reason_tag"] = reason_tag

    # If reason looks casual/frivolous => auto reject (even if capacity is ok)
    if reason_tag["category"] == "FRIVOLOUS":
        safe_base.update({
            "decision": "REJECT",
            "risk": 95,
            "level": "HIGH",
            "reasons": [
                "Rejected: Reason classified as non-serious/casual.",
                f"Reason analysis: {reason_tag['note']}",
            ],
        })
        return safe_base

    # ---- Compute components ----
    cap_after = cap_after_gate  # reuse computed value

    cap_comp = capacity_score(cap_after, min_capacity)               # 0..40
    dl_comp = deadline_score(overlapping_deadlines, near_deadlines)  # 0..40
    dur_comp = duration_score(days_requested)                        # 0..20

    risk = min(100, cap_comp + dl_comp + dur_comp)
    level = risk_level_from_score(risk)

    # ---- Decision logic ----
    # Auto-approve only if low risk + no overlap deadlines
    if risk < 35 and overlapping_deadlines == 0:
        decision = "AUTO_APPROVE"
    else:
        decision = "ESCALATE"

    # If reason is VALID (medical/emergency), we make sure it is at least escalated (not auto-approve blocked here)
    # (We already gate-reject frivolous, but valid reasons get manager consideration.)
    if reason_tag["category"] == "VALID":
        # Keep auto-approve only if truly low-risk, else escalate (already happens).
        pass

    reasons = [
        f"Capacity after leave: {cap_after:.0%} (min allowed {min_capacity:.0%})",
        f"Deadlines (ESCALATE policy) overlap: {overlapping_deadlines}, near-window: {near_deadlines}",
        f"Working days requested: {days_requested}",
        f"Reason tag: {reason_tag['category']} ({reason_tag['note']})",
        f"Risk breakdown -> Capacity:{cap_comp} + Deadlines:{dl_comp} + Duration:{dur_comp} = {risk}",
    ]

    return {
        "decision": decision,
        "risk": int(risk),
        "level": level,
        "reasons": reasons,
        "capacity_after": cap_after,
        "components": {
            "capacity": int(cap_comp),
            "deadlines": int(dl_comp),
            "duration": int(dur_comp),
        },
        "reason_tag": reason_tag,
    }