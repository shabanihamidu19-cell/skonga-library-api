"""
SKONGA Library API — Subjects.json → Postgres Ingestion Adapter
================================================================
Reads the flat skonga-library content package (v0.07 style):

    Subjects.json                 # index of all subjects
    Subjects/{file}.json          # per-subject topics by form
    markdown/{notes}.md           # optional outline notes (may be empty)

and upserts into the Library API Postgres schema (subjects, forms,
subject_forms, topics).

This is the bridge between the CONTENT repo (source of truth) and the
API repo (runtime store). The two repos stay separate; this script is
the only coupling.

Run (from skonga-library-api repo root, with DATABASE_URL in .env):

    python3 ingestion/sync_from_subjects_json.py \\
        --content-dir /path/to/skonga-library

    # or:
    LIBRARY_CONTENT_DIR=/path/to/skonga-library \\
        python3 ingestion/sync_from_subjects_json.py

Optional flags:
    --dry-run     print what would be written, no DB writes
    --status      topic status to apply (default: published)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any

# Allow running from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


# ── Helpers ──────────────────────────────────────────────────────────────────

FORM_NAME_TO_ID: dict[str, int] = {
    "form i": 1,
    "form ii": 2,
    "form iii": 3,
    "form iv": 4,
    "form v": 5,
    "form vi": 6,
    "form 1": 1,
    "form 2": 2,
    "form 3": 3,
    "form 4": 4,
    "form 5": 5,
    "form 6": 6,
}


def parse_form_id(form_name: str) -> int | None:
    key = (form_name or "").strip().lower()
    key = re.sub(r"\s+", " ", key)
    if key in FORM_NAME_TO_ID:
        return FORM_NAME_TO_ID[key]
    m = re.search(r"\b([1-6]|i{1,3}|iv|v|vi)\b", key, re.I)
    if not m:
        return None
    token = m.group(1).lower()
    roman = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6}
    if token in roman:
        return roman[token]
    if token.isdigit():
        n = int(token)
        return n if 1 <= n <= 6 else None
    return None


def slugify(text: str, max_len: int = 48) -> str:
    """ASCII slug for topic ids — stable and URL-safe."""
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if not text:
        text = "topic"
    return text[:max_len].rstrip("-")


def topic_id(subject_id: str, form_id: int, order_index: int, title: str) -> str:
    return f"{subject_id}-f{form_id}-t{order_index:02d}-{slugify(title)}"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_topic_notes(notes_md: str, form_name: str, title: str) -> str | None:
    """
    Best-effort: pull a short note block for this topic from subject markdown.

    Markdown in v0.07 is mostly outlines (# Subject / ## Form / - Topic).
    If the topic title appears as a bullet, return a small contextual snippet.
    """
    if not notes_md or not notes_md.strip():
        return None

    # Prefer the Form section that matches form_name
    form_header = re.compile(
        rf"^##\s*{re.escape(form_name)}\s*$", re.I | re.M
    )
    sections = re.split(r"(?m)^##\s+", notes_md)
    body_for_form = notes_md
    for sec in sections:
        if sec.lower().startswith(form_name.lower().replace("form ", "")) or form_name.lower() in sec[:40].lower():
            # rough match
            pass

    # Find the bullet line containing the title
    pattern = re.compile(
        rf"^[\-\*]\s*{re.escape(title)}\s*$", re.I | re.M
    )
    m = pattern.search(notes_md)
    if not m:
        # softer match
        pattern2 = re.compile(re.escape(title), re.I)
        m = pattern2.search(notes_md)
        if not m:
            return None

    # Build a minimal educational stub the LLM can use
    return (
        f"Curriculum topic ({form_name}): {title}\n\n"
        f"This topic is part of the official secondary-school outline. "
        f"Explain concepts clearly for Tanzanian students (TIE syllabus), "
        f"with definitions, key points, and simple examples where helpful."
    )


def upsert_subject_row(
    db,
    subject_id: str,
    name: str,
    icon: str | None,
    today: date,
) -> None:
    from app.db.models import Subject
    existing = db.query(Subject).filter(Subject.id == subject_id).first()
    if existing:
        existing.name_en = name
        existing.name_sw = name  # content package has one display name
        existing.icon = icon
        existing.schema_version = 1
        existing.last_updated = today
    else:
        db.add(
            Subject(
                id=subject_id,
                name_en=name,
                name_sw=name,
                icon=icon,
                schema_version=1,
                last_updated=today,
            )
        )


def ensure_subject_form(db, subject_id: str, form_id: int) -> None:
    from app.db.models import SubjectForm
    exists = (
        db.query(SubjectForm)
        .filter(SubjectForm.subject_id == subject_id, SubjectForm.form_id == form_id)
        .first()
    )
    if not exists:
        db.add(SubjectForm(subject_id=subject_id, form_id=form_id))


def upsert_topic_row(
    db,
    *,
    tid: str,
    subject_id: str,
    form_id: int,
    order_index: int,
    title: str,
    content_md: str | None,
    status: str,
    today: date,
) -> None:
    from app.db.models import Topic
    existing = db.query(Topic).filter(Topic.id == tid).first()
    kwargs = dict(
        subject_id=subject_id,
        form_id=form_id,
        order_index=order_index,
        title_en=title,
        title_sw=title,
        competency_mkuu=None,
        tags=[],
        related_topics=[],
        difficulty="foundational" if form_id <= 2 else ("intermediate" if form_id <= 4 else "advanced"),
        status=status,
        content_version=1,
        last_updated=today,
        content_md=content_md,
    )
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
    else:
        db.add(Topic(id=tid, **kwargs))


# ── Main sync ────────────────────────────────────────────────────────────────

def sync(content_dir: Path, *, dry_run: bool = False, status: str = "published") -> int:
    content_dir = content_dir.resolve()
    index_path = content_dir / "Subjects.json"
    if not index_path.exists():
        print(f"[sync] ERROR: {index_path} not found", file=sys.stderr)
        print(
            "  Point --content-dir at the root of skonga-library "
            "(the folder that contains Subjects.json).",
            file=sys.stderr,
        )
        return 1

    index: list[dict] = load_json(index_path)
    if not isinstance(index, list) or not index:
        print("[sync] ERROR: Subjects.json must be a non-empty JSON array", file=sys.stderr)
        return 1

    print(f"[sync] Content dir: {content_dir}")
    print(f"[sync] Subjects in index: {len(index)}")
    print(f"[sync] Topic status: {status} | dry_run={dry_run}")

    Base = Form = Subject = SubjectForm = Topic = SessionLocal = engine = None
    if not dry_run:
        from app.db.models import Base, Form, Subject, SubjectForm, Topic
        from app.db.session import SessionLocal, engine

        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            for form_id in range(1, 7):
                if not db.query(Form).filter(Form.id == form_id).first():
                    db.add(Form(id=form_id))
            db.commit()
        finally:
            db.close()

    today = date.today()
    total_subjects = 0
    total_topics = 0
    skipped_forms = 0
    missing_files: list[str] = []
    errors: list[str] = []

    db = None if dry_run else SessionLocal()

    try:
        for entry in index:
            subject_id = (entry.get("id") or "").strip()
            name = (entry.get("name") or subject_id).strip()
            icon = entry.get("icon")
            rel_file = entry.get("file") or ""
            notes_rel = entry.get("notes_file")

            if not subject_id or not rel_file:
                errors.append(f"Index entry missing id/file: {entry}")
                continue

            subject_path = content_dir / rel_file
            if not subject_path.exists():
                missing_files.append(rel_file)
                errors.append(f"{subject_id}: file not found → {rel_file}")
                continue

            try:
                payload = load_json(subject_path)
            except Exception as exc:
                errors.append(f"{subject_id}: cannot parse {rel_file}: {exc}")
                continue

            forms_map = payload.get("forms") or {}
            if not isinstance(forms_map, dict):
                errors.append(f"{subject_id}: 'forms' must be an object")
                continue

            notes_md = ""
            if notes_rel:
                notes_path = content_dir / notes_rel
                if notes_path.exists():
                    notes_md = notes_path.read_text(encoding="utf-8")

            if dry_run:
                topic_count = sum(len(v) for v in forms_map.values() if isinstance(v, list))
                print(f"  [dry] {subject_id:36s} {name:30s} topics≈{topic_count}")
                total_subjects += 1
                total_topics += topic_count
                continue

            assert db is not None
            try:
                upsert_subject_row(db, subject_id, name, icon, today)

                for form_name, titles in forms_map.items():
                    form_id = parse_form_id(str(form_name))
                    if form_id is None:
                        skipped_forms += 1
                        errors.append(f"{subject_id}: unknown form label '{form_name}'")
                        continue
                    if not isinstance(titles, list):
                        errors.append(f"{subject_id} {form_name}: topics must be a list")
                        continue

                    ensure_subject_form(db, subject_id, form_id)

                    for order_index, title in enumerate(titles, start=1):
                        title = str(title).strip()
                        if not title:
                            continue
                        tid = topic_id(subject_id, form_id, order_index, title)
                        content_md = extract_topic_notes(notes_md, str(form_name), title)
                        if content_md is None:
                            # Always give the LLM a minimal curriculum anchor
                            content_md = (
                                f"Curriculum topic: {title}\n"
                                f"Subject: {name} | {form_name}\n\n"
                                f"Align the explanation with the Tanzania secondary "
                                f"school (TIE) syllabus outline for this topic."
                            )
                        upsert_topic_row(
                            db,
                            tid=tid,
                            subject_id=subject_id,
                            form_id=form_id,
                            order_index=order_index,
                            title=title,
                            content_md=content_md,
                            status=status,
                            today=today,
                        )
                        total_topics += 1

                db.commit()
                total_subjects += 1
                print(f"  [ok] {subject_id}")
            except Exception as exc:
                db.rollback()
                errors.append(f"{subject_id}: {exc}")
    finally:
        if db is not None:
            db.close()

    print(
        f"\n[sync] Done: {total_subjects} subjects, {total_topics} topics"
        + (f", {skipped_forms} unknown form labels" if skipped_forms else "")
    )
    if missing_files:
        print(f"[sync] Missing subject files: {len(missing_files)}")
    if errors:
        print(f"[sync] {len(errors)} warning(s)/error(s):")
        for e in errors[:30]:
            print(f"  - {e}")
        if len(errors) > 30:
            print(f"  … and {len(errors) - 30} more")
        # Non-zero only if nothing was ingested
        return 0 if total_subjects else 1

    print("[sync] ✅ Database is in sync with Subjects.json content.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest skonga-library Subjects.json content into Library API Postgres"
    )
    parser.add_argument(
        "--content-dir",
        default=os.environ.get("LIBRARY_CONTENT_DIR", ""),
        help="Path to skonga-library root (folder containing Subjects.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report only — do not write to the database",
    )
    parser.add_argument(
        "--status",
        default="published",
        choices=["skeleton", "draft", "reviewed", "published"],
        help="Status to set on all ingested topics (default: published, so RAG can find them)",
    )
    args = parser.parse_args(argv)

    if not args.content_dir:
        print(
            "[sync] ERROR: pass --content-dir /path/to/skonga-library "
            "or set LIBRARY_CONTENT_DIR",
            file=sys.stderr,
        )
        return 1

    return sync(Path(args.content_dir), dry_run=args.dry_run, status=args.status)


if __name__ == "__main__":
    raise SystemExit(main())
