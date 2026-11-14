"""Progress summaries from explicitly recorded completed study sets."""


def practice_topic_summaries(sessions):
    groups = {}
    for session in sessions:
        key = (session.subject.strip().casefold(), session.topic.strip().casefold())
        group = groups.setdefault(key, {
            "subject": session.subject.strip(), "topic": session.topic.strip(),
            "sessions": [], "correct": 0, "incorrect": 0, "blank": 0,
        })
        group["sessions"].append(session)
        for field in ("correct", "incorrect", "blank"):
            group[field] += getattr(session, field)

    summaries = []
    for group in groups.values():
        ordered = sorted(group.pop("sessions"), key=lambda item: (item.date, item.created_at, item.id))
        answered = group["correct"] + group["incorrect"]
        group["session_count"] = len(ordered)
        group["answered"] = answered
        group["net"] = sum(session.net for session in ordered)
        group["accuracy"] = group["correct"] / answered if answered else None
        group["trend"] = [{
            "id": session.id,
            "date": session.date,
            "net": session.net,
            "accuracy": session.accuracy,
        } for session in ordered]
        summaries.append(group)
    summaries.sort(key=lambda item: (item["subject"].casefold(), item["topic"].casefold()))
    return summaries
