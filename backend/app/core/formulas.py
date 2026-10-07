"""Core gamification formulas for Hamartia.

These are the canonical, project-wide formulas. They are imported by the API
layers so the math lives in exactly one place and cannot drift out of sync.
"""

# YKS net score. Each wrong answer costs 1/4 of one correct answer.
# Division is guarded: with zero answered items the net is defined as 0.0,
# never a zero-division error.
YKS_PENALTY_FACTOR = 4.0


def net_score(correct: int, incorrect: int) -> float:
    """Return the YKS net score for a given correct/incorrect split."""
    total_answered = correct + incorrect
    if total_answered <= 0:
        return 0.0
    return correct - (incorrect / YKS_PENALTY_FACTOR)


def xp_for_exam(exam) -> int:
    """XP from a single exam.

    Balances accuracy, net output and time efficiency:

        xp = max(0, int((net * correct * 1.5)
                        - (duration_minutes * incorrect * 0.25)))

    Faster exams (low duration_minutes) and higher accuracy yield more XP.
    Blank answers are intentionally ignored — only correct and incorrect
    drive the reward.
    """
    net = exam.net
    correct = exam.correct
    incorrect = exam.incorrect
    duration_minutes = exam.duration_minutes
    if duration_minutes <= 0:
        duration_minutes = 1  # avoid dividing out the time-efficiency bonus

    raw = (net * correct * 1.5) - (duration_minutes * incorrect * 0.25)
    # XP is never negative.
    return max(0, int(raw))


def level_for_xp(total_xp: int) -> int:
    """Map cumulative XP to a level using a linear-threshold ladder.

    Level 1 requires 0 XP. Reaching level N requires N * 500 XP total.
    """
    if total_xp < 0:
        total_xp = 0
    if total_xp < 500:
        return 1
    return max(1, (total_xp // 500) + 1)


def average_net(exams) -> float:
    """Average net score across all exams. Guards against empty history."""
    if not exams:
        return 0.0
    return sum(e.net for e in exams) / len(exams)
