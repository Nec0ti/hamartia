"""Deterministic profile progression derived from saved exam history."""

from datetime import date, timedelta

from app.core.formulas import level_for_xp


def progression_summary(exams, bonus_xp=0, today=None):
    today = today or date.today()
    exam_xp = sum(exam.xp for exam in exams)
    dates = set()
    for exam in exams:
        try:
            dates.add(date.fromisoformat(exam.date))
        except ValueError:
            continue

    last_active = max((day for day in dates if day <= today), default=None)
    streak = 0
    if last_active and last_active >= today - timedelta(days=1):
        day = last_active
        while day in dates:
            streak += 1
            day -= timedelta(days=1)

    total_xp = max(0, bonus_xp) + exam_xp
    return {
        "total_xp": total_xp,
        "level": level_for_xp(total_xp),
        "streak_days": streak,
        "last_active_date": last_active.isoformat() if last_active else "",
    }
