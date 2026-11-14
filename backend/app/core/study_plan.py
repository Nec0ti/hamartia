"""Deterministic study priorities derived from the local mistake vault."""

from collections import Counter


def topic_priorities(questions):
    groups = {}
    for question in questions:
        subject = question.subject.strip() or "Ders belirtilmedi"
        topic = question.topic.strip() or "Konu belirtilmedi"
        key = (subject.casefold(), topic.casefold())
        group = groups.setdefault(key, {
            "subject": subject,
            "topic": topic,
            "question_count": 0,
            "last_seen": "",
            "tags": Counter(),
        })
        group["question_count"] += 1
        group["last_seen"] = max(group["last_seen"], question.created_at[:10])
        group["tags"][question.hamartia_tag] += 1

    topics = [
        {**group, "tags": dict(group["tags"])}
        for group in groups.values()
    ]
    topics.sort(key=lambda group: (-group["question_count"], group["subject"].casefold(), group["topic"].casefold()))
    return {
        "total_questions": len(questions),
        "unclassified_questions": sum(not q.subject.strip() or not q.topic.strip() for q in questions),
        "topics": topics,
    }
