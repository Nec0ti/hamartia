"""Deterministic study priorities derived from the local mistake vault."""

from collections import Counter


def topic_priorities(questions):
    groups = {}
    pending_questions = 0
    unclassified_questions = 0
    for question in questions:
        if question.reviewed_at:
            continue
        pending_questions += 1
        unclassified_questions += not question.subject.strip() or not question.topic.strip()
        subject = question.subject.strip() or "Ders belirtilmedi"
        topic = question.topic.strip() or "Konu belirtilmedi"
        key = (subject.casefold(), topic.casefold())
        group = groups.setdefault(key, {
            "subject": subject,
            "topic": topic,
            "pending_count": 0,
            "last_seen": "",
            "tags": Counter(),
        })
        group["pending_count"] += 1
        group["last_seen"] = max(group["last_seen"], question.created_at[:10])
        group["tags"][question.hamartia_tag] += 1

    topics = [
        {**group, "tags": dict(group["tags"])}
        for group in groups.values()
    ]
    topics.sort(key=lambda group: (-group["pending_count"], group["subject"].casefold(), group["topic"].casefold()))
    return {
        "total_questions": len(questions),
        "pending_questions": pending_questions,
        "unclassified_questions": unclassified_questions,
        "topics": topics,
    }
