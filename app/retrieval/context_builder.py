"""
SKONGA Library API — Context Builder
=======================================
Takes raw search results (topic dicts) and assembles them into an LLM-ready
context string and a list of citations for the AI backend/UI.
"""
from typing import Any, List, Tuple


CONTEXT_HEADER = (
    "The following educational content is retrieved from the official SKONGA Library, "
    "which aligns with the Tanzania Institute of Education (TIE) curriculum. "
    "Use this information as curriculum-aligned context when answering the student's question.\n\n"
    "---\n"
)

CONTEXT_FOOTER = (
    "\n---\n"
    "When answering, reference the curriculum-aligned content above where relevant. "
    "If a question falls outside what's covered above, answer from general knowledge but note it is not curriculum-aligned."
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _format_topic(topic: dict, include_content: bool = True) -> str:
    """
    Format a single topic dict into a human-readable block for LLM context.
    Uses .get(...) everywhere to avoid KeyError when fields are missing.
    """
    title_sw = _safe_str(topic.get("title_sw") or topic.get("title_en") or "(untitled)")
    title_en = _safe_str(topic.get("title_en") or topic.get("title_sw") or "(untitled)")

    form_name = f"Form {topic.get('form_id')}" if topic.get("form_id") else ""
    subject = _safe_str(topic.get("subject_id", "")).replace("-", " ").title()
    difficulty = _safe_str(topic.get("difficulty", "")).capitalize()

    lines = [
        f"TOPIC: {title_sw} / {title_en}",
        f"Subject: {subject} | {form_name} | Difficulty: {difficulty}",
    ]

    # Include curriculum-aligned notes if available (content_md on topic)
    content = _safe_str(topic.get("content_md", ""))
    if include_content and content.strip():
        # Remove top-level markdown headings for cleaner injection
        clean = content.replace("##", "").replace("#", "").strip()
        lines.append(f"Notes:\n{clean}")

    return "\n".join(lines)


def build_context(
    topics: List[dict],
    retrieval_mode: str = "fulltext",
    include_content: bool = True,
) -> Tuple[str, List[dict]]:
    """
    Build the AI-ready context string and citations from a list of topics.

    Returns:
        context_text: full string ready to inject into LLM system prompt
        citations: list of {topic_id, title_sw, title_en, relevance, subject_id, form_id}
    """
    if not topics:
        return "", []

    blocks = []
    citations = []

    for i, topic in enumerate(topics, start=1):
        try:
            blocks.append(f"[{i}] {_format_topic(topic, include_content=include_content)}")
            citations.append({
                "topic_id": _safe_str(topic.get("id")),
                "title_sw": _safe_str(topic.get("title_sw") or topic.get("title_en")),
                "title_en": _safe_str(topic.get("title_en") or topic.get("title_sw")),
                "subject_id": topic.get("subject_id"),
                "form_id": topic.get("form_id"),
                "relevance": round(float(topic.get("relevance", 0.0)), 4),
            })
        except Exception:
            # Skip malformed topics but continue building context for others
            continue

    context_text = CONTEXT_HEADER + "\n\n".join(blocks) + CONTEXT_FOOTER

    return context_text, citations
