"""Fielding rating calculator.

Fielding starts at a neutral 5.0 base.
Events push the rating up or down.
"""

from __future__ import annotations

from typing import List

from .models import FieldingEvent, FieldingEventType


# Points per fielding event
EVENT_POINTS = {
    FieldingEventType.CATCH: 0.4,
    FieldingEventType.DIRECT_RUN_OUT: 1.5,
    FieldingEventType.ASSISTED_RUN_OUT: 0.75,
    FieldingEventType.STUMPING: 1.0,
    FieldingEventType.DROPPED_CATCH: -1.5,
    FieldingEventType.MISFIELD: -0.5,
}


def calculate_fielding_rating(
    player_name: str,
    events: List[FieldingEvent],
) -> tuple[float, dict]:
    """Calculate a fielding rating from 0-10.

    Returns:
        (rating, details_dict) with breakdown.
    """
    base = 5.0
    total_adjustment = 0.0
    event_details: list[dict] = []

    player_events = [e for e in events if e.player_name == player_name]

    for event in player_events:
        points = EVENT_POINTS.get(event.event_type, 0.0)
        total_adjustment += points
        event_details.append({
            "type": event.event_type.value,
            "points": points,
        })

    total = base + total_adjustment
    total = max(0.0, min(10.0, total))
    total = round(total, 1)

    details = {
        "events": event_details,
        "adjustment": round(total_adjustment, 2),
        "total": total,
        "has_events": len(player_events) > 0,
    }

    return total, details
