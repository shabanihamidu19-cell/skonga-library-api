"""
SKONGA Library API — Context Builder
=======================================
Takes raw search results (topic dicts) and assembles them into a single
structured text block suitable for injection into an LLM context/system
prompt. Also builds the citations list returned to the AI backend.

This is the bridge between "retrieval" (getting topics) and
"generation" (the LLM producing an answer). Keeping it separate from
both makes it easy to tune the output format without touching retrieval
or API logic.
"""
from typing import Any


CONTEXT_HEADER = """The following educational content is retrieved from the official SKONGA Library, which is based on the Tanzania Institute of Education (TIE) curriculum. Use this information to ensure your answer aligns with the official Tanzanian secondary school syllabus when relevant.

---
"""

CONTEXT_FOOTER = """
---
When answering, reference the curriculum-aligned content above where relevant. If a question falls outside what's covered above, answer from your general knowledge but note it is not curriculum-specific.
"""


def _format_topic(topic: dict, include_content: bool = True) -> str:
    """
    Format a single topic dict into a human-readable block for LLM context.
    """
    form_name = f"Form {topic['form_id']}" if topic.get("form_id") else ""
    subject = topic.get("subject_id", "").replace("-", " ").title()
    difficulty = topic.get("difficulty", "")

    lines = [
        f"TOPIC: {topic['title_sw']} / {topic['title_en']}",
        f"Subject: {subject} | {form_name} | Difficulty: {difficulty}",
    ]

    # Include curriculum-aligned notes if available (content_md on topic)
    content = topic.get("content_md") or ""
    if include_content and content.strip():
        # Strip raw markdown headings for cleaner LLM injection
        clean = content.replace("##", "").replace("#", "").strip()
        lines.append(f"Notes:\n{clean}")

    return "\n".join(lines)


def build_context(
    topics: list[dict],
    retrieval_mode: str = "fulltext",
    include_content: bool = True,
) -> tuple[str, list[dict]]:
    """
    Build the AI-ready context string and citations from a list of topics.

    Returns:
        context_text: full string ready to inject into LLM system prompt
        citations: list of {topic_id, title_sw, title_en, relevance}
                   for the AI backend to surface in the UI as "sources"
    """
    if not topics:
        return "", []

    blocks = []
    citations = []

    for i, topic in enumerate(topics, start=1):
        blocks.append(f"[{i}] {_format_topic(topic, include_content=include_content)}")
        citations.append({
            "topic_id": topic["id"],
            "title_sw": topic["title_sw"],
            "title_en": topic["title_en"],
            "subject_id": topic.get("subject_id"),
            "form_id": topic.get("form_id"),
            "relevance": round(float(topic.get("relevance", 0.0)), 4),
        })

    context_text = (
        CONTEXT_HEADER
        + "\n\n".join(blocks)
        + CONTEXT_FOOTER
    )

    return context_text, citations
