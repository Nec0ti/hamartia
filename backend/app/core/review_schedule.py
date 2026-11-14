"""Deterministic spaced review dates from locally recorded solve attempts."""

from datetime import date, datetime, timedelta

REVIEW_INTERVALS = (1, 3, 7, 14, 30)


def _attempt_day(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (AttributeError, ValueError):
        return None


def review_state(question, today=None):
    """Return the due date and correctness streak without mutating a question."""
    today = today or date.today()
    attempts = question.review_attempts
    if question.reviewed_at:
        return {"due_date": "", "due": False, "streak": 0, "last_correct": None}
    if not attempts:
        return {"due_date": today.isoformat(), "due": True, "streak": 0, "last_correct": None}

    last = attempts[-1]
    last_day = _attempt_day(last.attempted_at)
    if last_day is None:
        return {"due_date": today.isoformat(), "due": True, "streak": 0, "last_correct": last.correct}

    streak = 0
    for attempt in reversed(attempts):
        if not attempt.correct:
            break
        streak += 1
    interval = REVIEW_INTERVALS[min(streak - 1, len(REVIEW_INTERVALS) - 1)] if streak else 1
    due_date = last_day + timedelta(days=interval)
    return {
        "due_date": due_date.isoformat(),
        "due": due_date <= today,
        "streak": streak,
        "last_correct": last.correct,
    }
