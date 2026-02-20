from datetime import date, timedelta
from typing import Dict, Any


def business_days(start: date, end: date) -> int:
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
    if team_size <= 0:
        return 1.0
    available = max(team_size - people_on_leave, 0)
    return available / team_size


def capacity_score(capacity_after: float, min_threshold: float) -> int:
    if capacity_after < min_threshold:
        return 40
    if capacity_after >= 0.90:
        return 0
    span = 0.90 - min_threshold
    if span <= 0:
        return 10
    ratio = (0.90 - capacity_after) / span
    return int(max(0, min(40, ratio * 40)))


def deadline_score(overlapping_deadlines: int, near_deadlines: int) -> int:
    score = 0
    score += min(overlapping_deadlines * 25, 40)
    score += min(near_deadlines * 10, 20)
    return int(min(score, 40))


def duration_score(days_requested: int) -> int:
    if days_requested <= 1:
        return 2
    if days_requested <= 3:
        return 8
    if days_requested <= 5:
        return 14
    return 20


def risk_level_from_score(risk: int) -> str:
    if risk >= 85:
        return "CRIT"
    if risk >= 70:
        return "HIGH"
    if risk >= 35:
        return "MED"
    return "LOW"


def evaluate_leave(
    balance: float,
    days_requested: int,
    team_size: int,
    current_approved_leaves: int,
    min_capacity: float,
    overlapping_deadlines: int,     # deadlines with policy ESCALATE
    near_deadlines: int,
    hard_block_overlaps: int,       # NEW: deadlines with policy HARD_BLOCK
) -> Dict[str, Any]:

    safe_base = {
        "decision": "ESCALATE",
        "risk": 0,
        "level": "LOW",
        "reasons": [],
        "capacity_after": 1.0,
        "components": {"capacity": 0, "deadlines": 0, "duration": 0},
    }

    # Hard rejection 1: invalid/0 days
    if days_requested <= 0:
        safe_base.update({
            "decision": "REJECT",
            "risk": 100,
            "level": "CRIT",
            "reasons": ["Invalid date range or 0 working days."],
        })
        return safe_base

    # Hard rejection 2: balance
    if balance < days_requested:
        safe_base.update({
            "decision": "REJECT",
            "risk": 100,
            "level": "CRIT",
            "reasons": [f"Insufficient leave balance. Required={days_requested}, Available={balance}"],
        })
        return safe_base

    # Hard rejection 3 (NEW): overlaps a HARD_BLOCK deadline
    if hard_block_overlaps > 0:
        safe_base.update({
            "decision": "REJECT",
            "risk": 100,
            "level": "CRIT",
            "reasons": [f"Leave overlaps {hard_block_overlaps} HARD-BLOCK deadline(s). Policy: Auto-Reject."],
        })
        return safe_base

    # Compute components
    cap_after = capacity_after_leave(team_size, current_approved_leaves + 1)

    cap_comp = capacity_score(cap_after, min_capacity)               # 0..40
    dl_comp = deadline_score(overlapping_deadlines, near_deadlines)  # 0..40
    dur_comp = duration_score(days_requested)                        # 0..20

    risk = min(100, cap_comp + dl_comp + dur_comp)
    level = risk_level_from_score(risk)

    # Decision
    if risk < 35 and cap_after >= min_capacity and overlapping_deadlines == 0:
        decision = "AUTO_APPROVE"
    else:
        decision = "ESCALATE"

    reasons = [
        f"Capacity after leave: {cap_after:.0%} (min allowed {min_capacity:.0%})",
        f"Deadlines (escalate-policy) overlap: {overlapping_deadlines}, near-window: {near_deadlines}",
        f"Working days requested: {days_requested}",
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
    }