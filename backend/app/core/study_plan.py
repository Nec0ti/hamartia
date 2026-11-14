"""Deterministic study priorities derived from the local mistake vault."""

from collections import Counter
from datetime import date
from statistics import median

from app.core.review_schedule import attempt_day, review_state


def _question_order_insights(questions, exams):
    exam_by_id = {exam.id: exam for exam in exams}
    groups = {}
    labels = ("early", "middle", "late")
    for question in questions:
        exam = exam_by_id.get(question.exam_id)
        if not exam or question.solve_order is None:
            continue
        size = exam.correct + exam.incorrect + exam.blank
        if size < 1 or question.solve_order > size:
            continue
        key = (getattr(exam, "exam_type", "branch"), exam.subject)
        group = groups.setdefault(key, {"exam_ids": set(), **{label: {"wrong_count": 0, "times": []} for label in labels}})
        stage = labels[min(2, ((question.solve_order - 1) * 3) // size)]
        group["exam_ids"].add(exam.id)
        group[stage]["wrong_count"] += 1
        if question.time_spent_seconds is not None:
            group[stage]["times"].append(question.time_spent_seconds)

    result = []
    for (exam_type, subject), group in groups.items():
        row = {"exam_type": exam_type, "subject": subject, "exam_count": len(group["exam_ids"])}
        for label in labels:
            data = group[label]
            row[label] = {
                "wrong_count": data["wrong_count"],
                "median_seconds": median(data["times"]) if data["times"] else None,
            }
        result.append(row)
    result.sort(key=lambda row: (-sum(row[label]["wrong_count"] for label in labels), row["subject"].casefold(), row["exam_type"]))
    return result


def topic_priorities(questions, today=None, exams=()):
    today = today or date.today()
    groups = {}
    pending_questions = 0
    scheduled_questions = 0
    unclassified_questions = 0
    reviews = []
    today_question_ids = set()
    today_correct = 0
    today_incorrect = 0
    for question in questions:
        for attempt in question.review_attempts:
            if attempt_day(attempt.attempted_at) == today:
                today_question_ids.add(question.id)
                if attempt.correct:
                    today_correct += 1
                else:
                    today_incorrect += 1
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
        "today_questions": len(today_question_ids),
        "today_correct": today_correct,
        "today_incorrect": today_incorrect,
        "question_order": _question_order_insights(questions, exams),
        "topics": topics,
        "reviews": reviews,
    }
