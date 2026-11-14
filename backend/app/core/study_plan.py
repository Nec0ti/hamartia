"""Deterministic study priorities derived from the local mistake vault."""

from collections import Counter
from datetime import date

from app.core.review_schedule import review_state


def topic_priorities(questions, today=None):
    today = today or date.today()
    groups = {}
    pending_questions = 0
    scheduled_questions = 0
    unclassified_questions = 0
    reviews = []
    for question in questions:
        state = review_state(question, today=today)
        if not state["due"]:
            if state["due_date"]:
                scheduled_questions += 1
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
        reviews.append({
            "id": question.id,
            "subject": subject,
            "topic": topic,
            "hamartia_tag": question.hamartia_tag,
            "ocr_text": question.ocr_text,
            "has_image": bool(question.image_path),
            **state,
        })

    topics = [
        {**group, "tags": dict(group["tags"])}
        for group in groups.values()
    ]
    topics.sort(key=lambda group: (-group["pending_count"], group["subject"].casefold(), group["topic"].casefold()))
    reviews.sort(key=lambda item: (item["due_date"], item["subject"].casefold(), item["topic"].casefold(), item["id"]))
    return {
        "total_questions": len(questions),
        "pending_questions": pending_questions,
        "scheduled_questions": scheduled_questions,
        "unclassified_questions": unclassified_questions,
        "topics": topics,
        "reviews": reviews,
    }
